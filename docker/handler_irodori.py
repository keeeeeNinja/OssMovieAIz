"""RunPod Serverless handler for Irodori-TTS（案A：1エンドポイント・mode切替）.

正本仕様: serverless_bundle/IRODORI_ENDPOINT_SPEC.md

Input schema (JSON in event["input"]):
  mode:  "plain" | "clone" | "design"   (default: "plain")
  text:  str                            (required, 読み上げ本文)
  -- mode-specific --
  ref_audio: base64-encoded WAV bytes   (required for "clone")
  caption:   str                        (required for "design"; 声デザインのスタイル文)
  -- generation params (optional, all modes) --
  num_candidates: int   (default 1; >1 で候補をまとめて生成)
  seed:           int   (省略=ランダム)
  num_steps:      int   (default 40)
  seconds:        float (手動尺・省略=自動)
  duration_scale: float (default 1.0)
  cfg_scale_text / cfg_scale_caption / cfg_scale_speaker: float

Output:
  # num_candidates == 1 : base64 インライン
  { "audio": <base64 WAV>, "sample_rate": int, "duration_sec": float, "seed": int }
  # num_candidates > 1  : Volume(outputs/irodori/<job>/) に書き出しキー返却
  { "candidates": [ {"key": "outputs/irodori/<job>/cand_01.wav", "duration_sec": .., "seed": ..}, ... ],
    "sample_rate": int }
  # エラー
  { "error": str }
"""

import base64
import io
import os
import tempfile
import uuid

import runpod
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download

from irodori_tts.inference_runtime import (
    InferenceRuntime,
    RuntimeKey,
    SamplingRequest,
    save_wav,
)

# mode → checkpoint repo（plain/clone は 500M、design は 600M-VoiceDesign）
MODEL_REPOS = {
    "plain":  "Aratako/Irodori-TTS-500M-v3",
    "clone":  "Aratako/Irodori-TTS-500M-v3",
    "design": "Aratako/Irodori-TTS-600M-v3-VoiceDesign",
}
CODEC_REPO = "Aratako/Semantic-DACVAE-Japanese-32dim"

# Volume 上の複数候補書き出し先（root からの相対キーで返す）
VOLUME_ROOT = "/runpod-volume"
OUTPUT_SUBDIR = "outputs/irodori"

# InferenceRuntime を repo 単位でプロセス常駐キャッシュ（ウォームリクエストで再利用）
_runtimes = {}


def _device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def _precision():
    # GPU 前提で bf16（infer.py 既定の fp32 から変更）。CPU では fp32。
    return "bf16" if torch.cuda.is_available() else "fp32"


def get_runtime(mode):
    repo = MODEL_REPOS.get(mode)
    if repo is None:
        raise ValueError(f"unknown mode: {mode}; must be one of {list(MODEL_REPOS)}")
    if repo not in _runtimes:
        # HF_HOME=/runpod-volume/hf_cache 前提。Volume 常駐なら DL 済みキャッシュを引く。
        print(f"[handler] loading {repo} (device={_device()}, prec={_precision()})", flush=True)
        ckpt = hf_hub_download(repo_id=repo, filename="model.safetensors")
        _runtimes[repo] = InferenceRuntime.from_key(
            RuntimeKey(
                checkpoint=ckpt,
                model_device=_device(),
                codec_repo=CODEC_REPO,
                model_precision=_precision(),
                codec_device=_device(),
                codec_precision=_precision(),
                codec_deterministic_encode=True,
                codec_deterministic_decode=True,
                compile_model=False,
                compile_dynamic=False,
            )
        )
        print(f"[handler] {repo} loaded", flush=True)
    return _runtimes[repo]


def _build_request(inp, mode, ref_wav_path):
    """入力 → SamplingRequest。mode により caption / ref_wav / no_ref を出し分け。"""
    kwargs = dict(
        text=inp["text"],
        num_candidates=int(inp.get("num_candidates", 1)),
        num_steps=int(inp.get("num_steps", 40)),
        seed=inp.get("seed"),
        duration_scale=float(inp.get("duration_scale", 1.0)),
    )
    if inp.get("seconds") is not None:
        kwargs["seconds"] = float(inp["seconds"])
    for k in ("cfg_scale_text", "cfg_scale_caption", "cfg_scale_speaker"):
        if k in inp:
            kwargs[k] = float(inp[k])

    if mode == "clone":
        kwargs["ref_wav"] = ref_wav_path          # base64 → 一時 wav のパス
    elif mode == "design":
        kwargs["caption"] = inp["caption"]
        kwargs["no_ref"] = True                    # 声はデザイン（caption）で決める
    else:  # plain
        kwargs["no_ref"] = True                    # 500M はスピーカー条件付き → no_ref

    return SamplingRequest(**kwargs)


def _wav_bytes(audio, sample_rate):
    """torch.Tensor 音声 → WAV バイト列（save_wav 経由で正しい shape 処理）。"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        save_wav(tmp, audio, sample_rate)
        with open(tmp, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _duration(audio, sample_rate):
    n = audio.shape[-1] if hasattr(audio, "shape") else len(audio)
    return float(n) / float(sample_rate)


def handler(event):
    inp = event.get("input") or {}
    mode = inp.get("mode", "plain")
    text = inp.get("text", "")
    if not text:
        return {"error": "input.text is required"}
    if mode not in MODEL_REPOS:
        return {"error": f"unknown mode: {mode}; must be one of {list(MODEL_REPOS)}"}

    # mode 別の必須入力チェック
    ref_wav_path = None
    if mode == "clone":
        ref_b64 = inp.get("ref_audio", "")
        if not ref_b64:
            return {"error": "clone mode requires ref_audio (base64 wav)"}
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(base64.b64decode(ref_b64))
            ref_wav_path = f.name
    elif mode == "design":
        if not inp.get("caption"):
            return {"error": "design mode requires caption (style description)"}

    try:
        runtime = get_runtime(mode)
    except Exception as e:
        _cleanup(ref_wav_path)
        return {"error": f"model load failed: {e}"}

    try:
        req = _build_request(inp, mode, ref_wav_path)
        result = runtime.synthesize(req)
    except Exception as e:
        return {"error": f"generation failed: {e}"}
    finally:
        _cleanup(ref_wav_path)

    sr = int(result.sample_rate)
    audios = result.audios if getattr(result, "audios", None) else [result.audio]

    # 単一候補 → base64 インライン
    if len(audios) == 1:
        return {
            "audio": base64.b64encode(_wav_bytes(audios[0], sr)).decode("ascii"),
            "sample_rate": sr,
            "duration_sec": _duration(audios[0], sr),
            "seed": int(getattr(result, "used_seed", inp.get("seed") or -1)),
        }

    # 複数候補 → Volume に書き出してキー返却（レスポンスサイズ上限回避）
    job = str(event.get("id") or uuid.uuid4().hex)
    rel_dir = f"{OUTPUT_SUBDIR}/{job}"
    abs_dir = os.path.join(VOLUME_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    cands = []
    base_seed = int(getattr(result, "used_seed", 0))
    for i, audio in enumerate(audios, start=1):
        fname = f"cand_{i:02d}.wav"
        save_wav(os.path.join(abs_dir, fname), audio, sr)
        cands.append({
            "key": f"{rel_dir}/{fname}",
            "duration_sec": _duration(audio, sr),
            "seed": base_seed + (i - 1),
        })
    return {"candidates": cands, "sample_rate": sr}


def _cleanup(path):
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})

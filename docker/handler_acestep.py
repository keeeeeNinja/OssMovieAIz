"""RunPod Serverless handler for ACE-Step XL (BGM 生成)。

Input schema (event["input"]):
  caption:  str   (required) - 曲の説明テキスト（日英混在可）
  duration: int   (required) - 秒数（10〜600）
  bpm:      int   (optional) - デフォルト 120
  lyrics:   str   (optional) - 歌詞・構造ヒント
  seed:     int   (optional) - 再現性
  variant:  str   (optional) - "xl-turbo" / "xl-base" / "xl-sft"（デフォルト turbo）

Output:
  {"audio": base64 wav, "sample_rate": 44100, "duration_sec": float}
"""
import base64
import os
import sys
import tempfile
import traceback

import runpod
import torch

PROJECT_ROOT = "/workspace/ACE-Step-1.5"
sys.path.insert(0, PROJECT_ROOT)

# Lazy import 後段で行う（コールドスタート時のみロード）
_dit_handler = None
_llm_handler = None
_inference_module = None


def _ensure_loaded(variant: str = "xl-turbo"):
    global _dit_handler, _llm_handler, _inference_module
    if _dit_handler is not None:
        return

    print(f"[handler] loading ACE-Step XL ({variant})...", flush=True)
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    from acestep import inference as inference_module

    config_path = f"acestep-v15-{variant}"
    device = "cuda" if torch.cuda.is_available() else "cpu"

    dit = AceStepHandler()
    dit.initialize_service(
        project_root=PROJECT_ROOT,
        config_path=config_path,
        device=device,
    )
    llm = LLMHandler()
    llm.initialize(
        checkpoint_dir=os.environ.get("HF_HOME", "/runpod-volume/hf_cache"),
        lm_model_path="acestep-5Hz-lm-0.6B",
        backend="hf",  # vllm が無い場合は HuggingFace transformers backend
        device=device,
    )
    _dit_handler = dit
    _llm_handler = llm
    _inference_module = inference_module
    print("[handler] loaded.", flush=True)


def handler(event):
    inp = event.get("input") or {}
    caption = inp.get("caption", "")
    duration = int(inp.get("duration", 30))
    bpm = int(inp.get("bpm", 120))
    lyrics = inp.get("lyrics", "") or ""
    seed = inp.get("seed")
    variant = inp.get("variant", "xl-turbo")

    if not caption:
        return {"error": "caption is required"}
    if not (10 <= duration <= 600):
        return {"error": "duration must be 10..600"}

    try:
        _ensure_loaded(variant)
    except Exception as e:
        traceback.print_exc()
        return {"error": f"model load failed: {e}"}

    try:
        from acestep.inference import GenerationParams, GenerationConfig
        params_kwargs = {"caption": caption, "bpm": bpm, "duration": duration}
        if lyrics:
            params_kwargs["lyrics"] = lyrics
        if seed is not None:
            params_kwargs["seed"] = int(seed)
        params = GenerationParams(**params_kwargs)
        config = GenerationConfig(batch_size=1, audio_format="wav")

        with tempfile.TemporaryDirectory() as td:
            result = _inference_module.generate_music(
                _dit_handler, _llm_handler, params, config, save_dir=td,
            )
            if not getattr(result, "success", False):
                err = getattr(result, "error", "unknown") or "generation failed"
                return {"error": f"generate_music failed: {err}"}
            audios = getattr(result, "audios", []) or []
            if not audios:
                return {"error": "no audio returned"}
            audio = audios[0]
            wav_path = audio.get("path") if isinstance(audio, dict) else None
            if not wav_path or not os.path.isfile(wav_path):
                return {"error": "audio path missing"}
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()
            return {
                "audio": base64.b64encode(wav_bytes).decode("ascii"),
                "sample_rate": 44100,
                "duration_sec": float(duration),
                "seed": (audio.get("params", {}) or {}).get("seed") if isinstance(audio, dict) else None,
            }
    except Exception as e:
        traceback.print_exc()
        return {"error": f"generation failed: {e}"}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})

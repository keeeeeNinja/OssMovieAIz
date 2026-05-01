"""RunPod Serverless handler for Qwen3-TTS.

Input schema (JSON in event["input"]):
  mode:     "clone" | "preset" | "design"   (default: "preset")
  text:     str                              (required, target text to speak)
  language: str                              (default: "Japanese")
  -- mode-specific --
  ref_audio: base64-encoded WAV bytes        (required for "clone")
  ref_text:  str                             (required for "clone")
  speaker:   str  (e.g. "ono_anna")          (required for "preset")
  instruct:  str  (natural-language style)   (required for "design")
  -- generation params (optional, all modes) --
  do_sample, top_k, top_p, temperature, repetition_penalty

Output:
  {
    "audio":         base64-encoded WAV bytes,
    "sample_rate":   int,
    "duration_sec":  float,
  }
"""

import base64
import io
import os
import tempfile

import runpod
import soundfile as sf
import torch

from qwen_tts import Qwen3TTSModel

MODEL_IDS = {
    "clone":  "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "preset": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}

# Lazy-load and cache models in process memory across warm requests.
_models = {}


def _attn_impl():
    if not torch.cuda.is_available():
        return "sdpa"
    try:
        import flash_attn  # noqa: F401
        return "flash_attention_2"
    except Exception:
        return "sdpa"


def _device_map():
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def _dtype():
    return torch.bfloat16 if torch.cuda.is_available() else torch.float32


def get_model(mode):
    if mode not in MODEL_IDS:
        raise ValueError(f"unknown mode: {mode}; must be one of {list(MODEL_IDS)}")
    if mode not in _models:
        print(f"[handler] loading {MODEL_IDS[mode]} (attn={_attn_impl()})", flush=True)
        _models[mode] = Qwen3TTSModel.from_pretrained(
            MODEL_IDS[mode],
            device_map=_device_map(),
            dtype=_dtype(),
            attn_implementation=_attn_impl(),
        )
        print(f"[handler] {mode} loaded", flush=True)
    return _models[mode]


def _gen_kwargs(inp):
    """Optional sampling params from input."""
    out = {}
    for k in ("do_sample", "top_k", "top_p", "temperature", "repetition_penalty"):
        if k in inp:
            out[k] = inp[k]
    return out


def handler(event):
    inp = event.get("input") or {}
    mode = inp.get("mode", "preset")
    text = inp.get("text", "")
    language = inp.get("language", "Japanese")
    if not text:
        return {"error": "input.text is required"}

    try:
        model = get_model(mode)
    except Exception as e:
        return {"error": f"model load failed: {e}"}

    extra = _gen_kwargs(inp)

    try:
        if mode == "clone":
            ref_b64 = inp.get("ref_audio", "")
            ref_text = inp.get("ref_text", "")
            if not ref_b64 or not ref_text:
                return {"error": "clone mode requires ref_audio (base64 wav) and ref_text"}
            ref_bytes = base64.b64decode(ref_b64)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(ref_bytes)
                ref_path = f.name
            try:
                wavs, sr = model.generate_voice_clone(
                    text=text, language=language,
                    ref_audio=ref_path, ref_text=ref_text,
                    **extra,
                )
            finally:
                try: os.unlink(ref_path)
                except OSError: pass

        elif mode == "preset":
            speaker = inp.get("speaker", "ono_anna")
            wavs, sr = model.generate_custom_voice(
                text=text, language=language, speaker=speaker, **extra,
            )

        elif mode == "design":
            instruct = inp.get("instruct", "")
            if not instruct:
                return {"error": "design mode requires instruct (style description)"}
            wavs, sr = model.generate_voice_design(
                text=text, language=language, instruct=instruct, **extra,
            )

        else:
            return {"error": f"unknown mode: {mode}"}

    except Exception as e:
        return {"error": f"generation failed: {e}"}

    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    audio_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return {
        "audio": audio_b64,
        "sample_rate": int(sr),
        "duration_sec": float(len(wavs[0]) / sr),
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})

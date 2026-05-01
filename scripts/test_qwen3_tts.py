#!/usr/bin/env python3
"""Qwen3-TTS-12Hz-1.7B-CustomVoice をローカル（Mac MPS / CPU）で試聴。
モデル DL: 約 3.4 GB（初回のみ）。出力: /tmp/qwen3_tts_samples/{voice}.wav"""
import os
import sys
import numpy as np
import soundfile as sf
import torch

from qwen_tts import Qwen3TTSModel

TEXT = "今だけ限定、3秒であなたのお気に入りが見つかる、新しい体験を、ぜひお試しください。"
OUT_DIR = "/tmp/qwen3_tts_voicedesign"
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"

# Mac MPS は flash-attn 不可。eager / sdpa 使用
device = "mps" if torch.backends.mps.is_available() else "cpu"
dtype = torch.float16 if device == "mps" else torch.float32
print(f"device={device}, dtype={dtype}")

os.makedirs(OUT_DIR, exist_ok=True)
print(f"Loading {MODEL_ID} (initial DL ~3.4 GB)...")
model = Qwen3TTSModel.from_pretrained(
    MODEL_ID,
    device_map=device,
    dtype=dtype,
    attn_implementation="sdpa",
)
print("Loaded.")

# 5パターンの女性ボイス設計
DESIGNS = [
    ("v1_bright_young",  "20s Japanese female, bright and energetic, friendly commercial narrator, clear voice"),
    ("v2_calm_pro",      "30s Japanese female, calm and soothing, professional narrator, warm tone"),
    ("v3_cool_smart",    "20s Japanese female, intelligent and cool, slightly low-pitched, sophisticated"),
    ("v4_warm_motherly", "40s Japanese female, warm and motherly, gentle and caring tone"),
    ("v5_clear_clean",   "20s Japanese female, very clear and refreshing voice, bright but not childish, suitable for ads"),
]

for label, instruct in DESIGNS:
    print(f"\n=== {label}: {instruct}")
    try:
        wavs, sr = model.generate_voice_design(
            text=TEXT, language="Japanese", instruct=instruct,
        )
        out_path = os.path.join(OUT_DIR, f"{label}.wav")
        sf.write(out_path, wavs[0], sr)
        dur = len(wavs[0]) / sr
        print(f"  → {out_path} ({dur:.1f}s)")
    except Exception as e:
        print(f"  ❌ {e}")

print(f"\n✅ done. ls {OUT_DIR}")

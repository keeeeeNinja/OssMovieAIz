#!/usr/bin/env python3
"""Kokoro TTS で日本語ボイスのサンプルを全5種生成。
出力: /tmp/kokoro_samples/{voice}.wav"""
import os
import sys

import soundfile as sf
from kokoro import KPipeline

TEXT = "今だけ限定、3秒であなたのお気に入りが見つかる、新しい体験を、ぜひお試しください。"
OUT_DIR = "/tmp/kokoro_samples"
VOICES = [
    ("jf_alpha", "女性 / 標準"),
    ("jf_gongitsune", "女性 / ごんぎつね（やや低め）"),
    ("jf_nezumi", "女性 / ねずみ（明るめ）"),
    ("jf_tebukuro", "女性 / 手袋（落ち着き）"),
    ("jm_kumo", "男性 / くも"),
]

os.makedirs(OUT_DIR, exist_ok=True)
print("Initializing Kokoro pipeline (lang_code='j')...")
pipeline = KPipeline(lang_code="j")

for voice_id, label in VOICES:
    print(f"\n[{voice_id}] {label}")
    out_path = os.path.join(OUT_DIR, f"{voice_id}.wav")
    audio_chunks = []
    generator = pipeline(TEXT, voice=voice_id, speed=1.0)
    for i, (gs, ps, audio) in enumerate(generator):
        audio_chunks.append(audio)
    if audio_chunks:
        import numpy as np
        full = np.concatenate(audio_chunks)
        sf.write(out_path, full, 24000)
        dur = len(full) / 24000
        print(f"  → {out_path} ({dur:.1f}s)")
    else:
        print(f"  ⚠️ no audio generated")

print(f"\n✅ done. ls {OUT_DIR}")

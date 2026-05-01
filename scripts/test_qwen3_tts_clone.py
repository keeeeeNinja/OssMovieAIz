#!/usr/bin/env python3
"""Qwen3-TTS Base で reference.wav の声をクローンし、指定テキストを発話。"""
import os
import sys
import torch
import soundfile as sf

REF_WAV = "QwenTTS/reference_qwen_female_v1.wav"
TARGET_TEXT = "ランポッドのサーバレスで画像生成と動画生成をします。"
OUT_DIR = "/tmp/qwen3_tts_clone"
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

os.makedirs(OUT_DIR, exist_ok=True)

# 1. Whisper で reference.wav を文字起こし
print("[1/2] Whisper で reference.wav を文字起こし中...")
from faster_whisper import WhisperModel
asr = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = asr.transcribe(REF_WAV, language="ja", beam_size=5)
ref_text = "".join(s.text for s in segments).strip()
print(f"  検出言語: {info.language} (確信度 {info.language_probability:.2f})")
print(f"  ref_text: 『{ref_text}』")

# 2. Qwen3-TTS Base モデルで声クローン
print(f"\n[2/2] {MODEL_ID} で声クローン生成中...")
from qwen_tts import Qwen3TTSModel

device = "mps" if torch.backends.mps.is_available() else "cpu"
dtype = torch.float16 if device == "mps" else torch.float32
model = Qwen3TTSModel.from_pretrained(
    MODEL_ID, device_map=device, dtype=dtype, attn_implementation="sdpa",
)

print(f"  target text: 『{TARGET_TEXT}』")
wavs, sr = model.generate_voice_clone(
    text=TARGET_TEXT,
    language="Japanese",
    ref_audio=REF_WAV,
    ref_text=ref_text,
)

out_path = os.path.join(OUT_DIR, "clone_output.wav")
sf.write(out_path, wavs[0], sr)
dur = len(wavs[0]) / sr
print(f"\n✅ 生成完了: {out_path} ({dur:.1f}s, sr={sr})")

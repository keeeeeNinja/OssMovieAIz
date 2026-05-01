"""[非推奨] Irodori-TTS は Non-Commercial License のため廃止しました。

商用利用OKの **Qwen3-TTS** に置き換え済みです。同じ用途なら以下を使ってください:

  python3 scripts/generate_tts_qwen3.py \\
    --text "テキスト" \\
    --reference QwenTTS/reference_qwen_female_v1.wav \\
    --output public/narration.wav

旧 CLI 互換のため、このファイルは引数を generate_tts_qwen3.py に転送します:
  --text  → そのまま
  --caption → --caption（design モードで使用）
  --reference → --reference（clone モードで使用）
  --output → そのまま
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

NEW_SCRIPT = Path(__file__).resolve().parent / "generate_tts_qwen3.py"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--caption", default=None)
    p.add_argument("--reference", default=None)
    # 旧引数（互換のため受け取るが Qwen3 では使わない）
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--cfg-scale-text", type=float, default=None)
    p.add_argument("--cfg-scale-caption", type=float, default=None)
    args = p.parse_args()

    print("⚠️  generate_tts_irodori.py は非推奨。商用ライセンス対応で Qwen3-TTS に切替済み。")
    print("    今後は scripts/generate_tts_qwen3.py を直接呼んでください。")
    print()

    cmd = [sys.executable, str(NEW_SCRIPT), "--text", args.text, "--output", args.output]
    if args.reference:
        cmd += ["--reference", args.reference]
    elif args.caption:
        cmd += ["--caption", args.caption]
    else:
        sys.exit("❌ --reference または --caption を指定してください")

    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()

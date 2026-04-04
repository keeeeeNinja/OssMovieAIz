"""
ナレーション音声生成スクリプト（Irodori-TTS VoiceDesign）

使い方:
  python3 scripts/generate_tts_irodori.py \
    --text "テキスト" \
    --caption "落ち着いた女性の声で、やわらかく自然に" \
    --output public/narration.wav

※ 初回実行時にモデルが自動ダウンロードされます（~1GB）
※ Apple Silicon (MPS) / CUDA / CPU に自動対応
"""
import argparse
import subprocess
import sys
from pathlib import Path

IRODORI_DIR = Path(__file__).resolve().parent.parent / "vendor" / "Irodori-TTS"
HF_CHECKPOINT = "Aratako/Irodori-TTS-500M-v2-VoiceDesign"


def main():
    parser = argparse.ArgumentParser(description="Irodori-TTS VoiceDesign ラッパー")
    parser.add_argument("--text", required=True, help="読み上げるテキスト")
    parser.add_argument("--caption", required=True, help="声質・感情の説明テキスト")
    parser.add_argument("--output", required=True, help="出力wavファイルパス")
    parser.add_argument("--steps", type=int, default=40, help="推論ステップ数（デフォルト: 40）")
    parser.add_argument("--seed", type=int, default=None, help="再現性用シード")
    parser.add_argument("--cfg-scale-text", type=float, default=3.0, help="テキストCFGスケール")
    parser.add_argument("--cfg-scale-caption", type=float, default=3.0, help="キャプションCFGスケール")
    args = parser.parse_args()

    if not IRODORI_DIR.exists():
        print(f"エラー: Irodori-TTSが見つかりません: {IRODORI_DIR}", file=sys.stderr)
        print("  git clone https://github.com/Aratako/Irodori-TTS.git vendor/Irodori-TTS", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "uv", "run", "python", "infer.py",
        "--hf-checkpoint", HF_CHECKPOINT,
        "--text", args.text,
        "--caption", args.caption,
        "--no-ref",
        "--output-wav", str(output_path),
        "--num-steps", str(args.steps),
        "--cfg-scale-text", str(args.cfg_scale_text),
        "--cfg-scale-caption", str(args.cfg_scale_caption),
    ]
    if args.seed is not None:
        cmd.extend(["--seed", str(args.seed)])

    print(f"モード: Irodori-TTS VoiceDesign")
    print(f"テキスト: {args.text}")
    print(f"キャプション: {args.caption}")
    print(f"ステップ数: {args.steps}")
    print("音声を生成中...")

    result = subprocess.run(cmd, cwd=str(IRODORI_DIR))
    if result.returncode != 0:
        print("エラー: 音声生成に失敗しました", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"完了: {output_path}")


if __name__ == "__main__":
    main()

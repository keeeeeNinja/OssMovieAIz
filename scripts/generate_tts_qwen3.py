"""ナレーション音声生成スクリプト（Qwen3-TTS Serverless 版）

旧 generate_tts_irodori.py の置き換え。Apache 2.0 で商用利用OK。
RunPod Serverless エンドポイント `RUNPOD_ENDPOINT_TTS` に投げて wav を取得する。

使い方:
  # voice cloning（推奨。リファレンスの声で合成）
  python3 scripts/generate_tts_qwen3.py \\
    --text "テキスト" \\
    --reference QwenTTS/reference_qwen_female_v1.wav \\
    --output public/narration.wav

  # voice design（リファレンス不要・声質を自然言語で指定）
  python3 scripts/generate_tts_qwen3.py \\
    --text "テキスト" \\
    --caption "20s Japanese female, bright and energetic, friendly commercial narrator" \\
    --output public/narration.wav

  # preset speaker（9種から選ぶ・最速）
  python3 scripts/generate_tts_qwen3.py \\
    --text "テキスト" \\
    --speaker ono_anna \\
    --output public/narration.wav

オプション:
  --reference-text  リファレンスwavの書き起こし。未指定時は Whisper で自動文字起こし。
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SERVERLESS_REQUEST = PROJECT_DIR / "scripts" / "serverless_request.py"


def transcribe(ref_audio: Path) -> str:
    """faster-whisper でリファレンス音声を日本語文字起こし。"""
    print(f"[whisper] ref_text 未指定 → {ref_audio.name} を文字起こし...")
    venv_py = PROJECT_DIR / ".venv-tts" / "bin" / "python"
    if not venv_py.is_file():
        sys.exit(
            "❌ .venv-tts が無いため自動文字起こしできません。\n"
            "   --reference-text で書き起こしを直接指定してください。"
        )
    code = (
        "import sys; from faster_whisper import WhisperModel; "
        "m = WhisperModel('base', device='cpu', compute_type='int8'); "
        f"segs, info = m.transcribe('{ref_audio}', language='ja', beam_size=5); "
        "print(''.join(s.text for s in segs).strip())"
    )
    r = subprocess.run([str(venv_py), "-c", code], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit("❌ Whisper 文字起こし失敗")
    text = r.stdout.strip()
    print(f"[whisper] ref_text: 『{text}』")
    return text


def main():
    p = argparse.ArgumentParser(description="Qwen3-TTS Serverless ナレーション生成")
    p.add_argument("--text", required=True, help="読み上げるテキスト")
    p.add_argument("--output", required=True, help="出力wavファイルパス")
    # 3 modes (排他)
    p.add_argument("--reference", default=None,
                   help="clone mode: リファレンスwavのパス。声質をこの声に揃える")
    p.add_argument("--reference-text", default=None,
                   help="clone mode: リファレンスの書き起こし。未指定なら Whisper 自動")
    p.add_argument("--caption", default=None,
                   help="design mode: 声質を自然言語で指定（例: '30s female, calm'）")
    p.add_argument("--speaker", default=None,
                   help="preset mode: 9 種の話者名 (aiden/ono_anna 等)")
    p.add_argument("--language", default="Japanese")
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--temperature", type=float, default=None)
    args = p.parse_args()

    if sum(bool(x) for x in (args.reference, args.caption, args.speaker)) != 1:
        sys.exit("❌ --reference / --caption / --speaker のいずれか1つを指定")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # serverless_request.py 経由で投入
    cmd = [
        sys.executable, str(SERVERLESS_REQUEST),
        "--endpoint", "tts",
        "--prompt-text", args.text,
        "--tts-language", args.language,
        "--timeout", str(args.timeout),
        "--save-locally",
    ]
    if args.temperature is not None:
        cmd += ["--tts-temperature", str(args.temperature)]

    if args.reference:
        ref_path = Path(args.reference).resolve()
        if not ref_path.is_file():
            sys.exit(f"❌ --reference が存在しません: {ref_path}")
        ref_text = args.reference_text or transcribe(ref_path)
        cmd += [
            "--tts-mode", "clone",
            "--tts-ref-audio", str(ref_path),
            "--tts-ref-text", ref_text,
        ]
        print(f"モード: clone (ref={ref_path.name})")
    elif args.caption:
        cmd += ["--tts-mode", "design", "--tts-instruct", args.caption]
        print(f"モード: design (caption='{args.caption}')")
    else:
        cmd += ["--tts-mode", "preset", "--tts-speaker", args.speaker]
        print(f"モード: preset (speaker={args.speaker})")

    print(f"テキスト: {args.text}")

    # 一時ディレクトリで生成 → 指定の output に rename
    with tempfile.TemporaryDirectory() as td:
        cmd += ["--output-root", td]
        print(f"投入: {' '.join(cmd[:6])} ...")
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(r.returncode)
        # serverless_request.py は tts_TEST.wav 等を作る
        candidates = list(Path(td).rglob("tts_*.wav"))
        if not candidates:
            sys.exit("❌ 生成された wav が見つかりません")
        shutil.move(str(candidates[0]), str(output_path))

    print(f"\n✅ 完了: {output_path}")


if __name__ == "__main__":
    main()

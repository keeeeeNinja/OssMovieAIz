#!/usr/bin/env python3
"""
バズ動画からテロップ確認用フレームを抽出する。

Usage:
  python3 scripts/extract_buzz_frames.py --url "https://youtube.com/shorts/xxx" [--timestamps 0.5,3.0,10.0]

出力: 作業中動画/buzz_ref/ にフレーム画像を保存
  - 指定タイムスタンプがない場合は動画を等間隔（2秒ごと）で自動抽出
  - Claude Codeで Read ツールを使って目視確認する
"""

import argparse
import json
import os
import subprocess
import sys


def download_video(url: str, output_path: str) -> bool:
    """yt-dlpで動画をダウンロード"""
    cmd = [
        "yt-dlp", "-f", "best[height<=1080]",
        "-o", output_path, "--no-warnings",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ダウンロードエラー: {result.stderr}", file=sys.stderr)
        return False
    return True


def get_resolution(video_path: str) -> tuple[int, int]:
    """動画の解像度を取得"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "stream=width,height",
        "-of", "json", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if "width" in stream and "height" in stream:
            return stream["width"], stream["height"]
    return 0, 0


def get_duration(video_path: str) -> float:
    """動画の長さを取得"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def extract_frames(video_path: str, output_dir: str, timestamps: list[float]) -> list[str]:
    """指定タイムスタンプでフレームを抽出"""
    os.makedirs(output_dir, exist_ok=True)
    extracted = []
    for t in timestamps:
        ts_str = f"{t:.1f}".replace(".", "_")
        out_file = os.path.join(output_dir, f"frame_{ts_str}s.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", str(t),
            "-i", video_path,
            "-frames:v", "1", "-q:v", "2",
            out_file
        ]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(out_file):
            extracted.append(out_file)
    return extracted


def main():
    parser = argparse.ArgumentParser(description="バズ動画テロップ確認用フレーム抽出")
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--timestamps", default="", help="抽出タイムスタンプ（カンマ区切り）。省略時は2秒間隔で自動抽出")
    parser.add_argument("--interval", default=2.0, type=float, help="自動抽出の間隔（秒）")
    args = parser.parse_args()

    base_dir = os.path.join(os.path.dirname(__file__), "../作業中動画")
    video_path = os.path.join(base_dir, "buzz_ref.mp4")
    output_dir = os.path.join(base_dir, "buzz_ref")

    # ダウンロード
    print(f"ダウンロード中: {args.url}")
    if not download_video(args.url, video_path):
        sys.exit(1)
    print(f"保存: {video_path}")

    # 長さ取得
    duration = get_duration(video_path)
    print(f"動画長: {duration:.1f}秒")

    # タイムスタンプ決定
    if args.timestamps:
        timestamps = [float(t) for t in args.timestamps.split(",")]
    else:
        timestamps = []
        t = 0.5
        while t < duration:
            timestamps.append(round(t, 1))
            t += args.interval

    # フレーム抽出
    print(f"フレーム抽出中（{len(timestamps)}枚）...")
    extracted = extract_frames(video_path, output_dir, timestamps)

    # 動画の解像度を取得
    video_w, video_h = get_resolution(video_path)

    # Remotion換算表を出力
    REMOTION_W, REMOTION_H = 1080, 1920

    # 結果
    print(f"\n{'=' * 50}")
    print(f"抽出完了: {len(extracted)}枚")
    print(f"保存先: {output_dir}/")
    print(f"参考動画解像度: {video_w}×{video_h}")
    print(f"Remotion解像度: {REMOTION_W}×{REMOTION_H}")
    print(f"{'=' * 50}")
    for f in extracted:
        print(f"  {os.path.basename(f)}")

    # テロップサイズ換算ガイド
    print(f"\n{'=' * 50}")
    print("テロップサイズ換算ガイド")
    print(f"{'=' * 50}")
    print("フレーム画像上のテキスト1文字の高さを目視で計測し、")
    print("以下の換算表でRemotionのfontSizeを算出してください。")
    print()
    print("  計算式: fontSize = (文字の高さpx / フレーム画像の高さpx) × Remotion高さ")
    print(f"  例: 文字高さ100px / フレーム高さ{video_h}px × {REMOTION_H}px = {int(100 / video_h * REMOTION_H)}px")
    print()
    print("  占有率 → Remotion fontSize 早見表:")
    for pct in [10, 15, 20, 25, 30]:
        px = int(REMOTION_H * pct / 100)
        print(f"    {pct}% → {px}px")
    print()
    print("確認項目:")
    print("  1. 縦書き/横書き")
    print("  2. フォント種類（丸ゴシック/角ゴシック/明朝/ポップ体）")
    print("  3. テキスト色・縁取り色")
    print("  4. 配置（左寄せ/中央/右寄せ）")
    print("  5. 文字サイズ（上の換算表で算出）")
    print("  6. テキストの実際の文言")


if __name__ == "__main__":
    main()

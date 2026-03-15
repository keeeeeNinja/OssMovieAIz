#!/usr/bin/env python3
"""
ACE-Step 1.5 音楽生成スクリプト
APIサーバー（localhost:8001）に接続して音楽を生成する。
30秒を超える場合は自動で分割生成+クロスフェード結合する。

使用前にAPIサーバーを起動してください:
    cd ~/Desktop/Dev/ACE-Step-1.5
    uv run acestep-api

使用例:
    # 15秒（1発生成）
    python3 scripts/generate_music.py \
        --caption "Calm acoustic guitar, warm and inviting" \
        --duration 15 \
        --output public/bgm.mp3

    # 60秒（自動で2パート分割+クロスフェード）
    python3 scripts/generate_music.py \
        --caption "Gentle acoustic guitar with light percussion, warm cinematic feel" \
        --duration 60 \
        --output public/bgm.mp3

    # 60秒・2パート別キャプション（前半穏やか→後半盛り上がり）
    python3 scripts/generate_music.py \
        --caption "Soft piano with gentle strings, calm and reflective" \
        --caption2 "Uplifting orchestral with piano, emotional crescendo" \
        --duration 60 \
        --output public/bgm.mp3
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time

import requests


BASE_URL = "http://localhost:8001"
MAX_SINGLE_DURATION = 30  # MPS OOM回避: これ以下なら1発生成
CROSSFADE_SEC = 5  # パート間のクロスフェード秒数


def check_health():
    try:
        res = requests.get(f"{BASE_URL}/health", timeout=5)
        res.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        return False


def generate_single(caption: str, lyrics: str, duration: int, output: str, label: str = ""):
    """1パート分を生成してファイルに保存する"""
    prefix = f"[{label}] " if label else ""

    print(f"{prefix}タスク投入中...")
    print(f"  caption : {caption}")
    print(f"  duration: {duration}秒")

    res = requests.post(f"{BASE_URL}/release_task", json={
        "caption": caption,
        "lyrics": lyrics,
        "duration": duration,
    }, timeout=30)
    res.raise_for_status()
    task_id = res.json()["data"]["task_id"]
    print(f"  task_id : {task_id}")

    print(f"{prefix}生成中...")
    attempt = 0
    while True:
        attempt += 1
        result = requests.post(f"{BASE_URL}/query_result", json={"task_id_list": [task_id]}, timeout=30)
        result.raise_for_status()
        data_list = result.json().get("data", [])
        item = next((d for d in data_list if d.get("task_id") == task_id), None)

        if item is None:
            print(f"  [{attempt}] タスク待機中...", end="\r")
            time.sleep(3)
            continue

        status = item.get("status", 0)
        if status == 1:
            import json as _json
            raw = item.get("result", "[]")
            audio_list = _json.loads(raw) if isinstance(raw, str) else raw
            audio_url = audio_list[0]["file"] if audio_list else None
            print(f"\n  完了 (試行回数: {attempt}回)")
            break
        elif status == 2:
            print(f"\nERROR: 生成に失敗しました: {item.get('progress_text', 'unknown error')}")
            sys.exit(1)
        else:
            progress = item.get("progress_text", "")
            print(f"  [{attempt}] 生成中... {progress[:40]}", end="\r")
            time.sleep(5)

    if not audio_url:
        print("ERROR: 音声URLが取得できませんでした")
        sys.exit(1)

    full_url = audio_url if audio_url.startswith("http") else f"{BASE_URL}{audio_url}"
    audio = requests.get(full_url, timeout=60)
    audio.raise_for_status()

    with open(output, "wb") as f:
        f.write(audio.content)

    size_kb = len(audio.content) / 1024
    print(f"  保存: {output} ({size_kb:.1f} KB)")


def crossfade_join(part1: str, part2: str, output: str, crossfade: int = CROSSFADE_SEC):
    """2つのMP3をクロスフェードで結合する"""
    print(f"クロスフェード結合中（{crossfade}秒）...")

    # part1の長さを取得
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", part1],
        capture_output=True, text=True
    )
    part1_dur = float(probe.stdout.strip())
    fade_out_start = part1_dur - crossfade
    delay_ms = int(fade_out_start * 1000)

    cmd = [
        "ffmpeg", "-y", "-i", part1, "-i", part2,
        "-filter_complex",
        f"[0]afade=t=out:st={fade_out_start}:d={crossfade}[a];"
        f"[1]afade=t=in:st=0:d={crossfade},adelay={delay_ms}|{delay_ms}[b];"
        f"[a][b]amix=inputs=2:duration=longest:normalize=0",
        "-ab", "192k", output
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: ffmpeg失敗: {result.stderr[:200]}")
        sys.exit(1)

    probe2 = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", output],
        capture_output=True, text=True
    )
    final_dur = float(probe2.stdout.strip())
    size_kb = os.path.getsize(output) / 1024
    print(f"  結合完了: {output} ({final_dur:.1f}秒, {size_kb:.1f} KB)")


def generate_music(caption: str, caption2: str, lyrics: str, duration: int, output: str):
    if not check_health():
        print("ERROR: APIサーバーに接続できません。")
        print("以下のコマンドでサーバーを起動してください:")
        print("  cd ~/Desktop/Dev/ACE-Step-1.5")
        print("  uv run acestep-api")
        sys.exit(1)

    if duration <= MAX_SINGLE_DURATION:
        # 30秒以下: 1発生成
        print(f"=== 1発生成モード（{duration}秒） ===")
        generate_single(caption, lyrics, duration, output)
    else:
        # 30秒超: 分割生成+クロスフェード
        part_dur = (duration + CROSSFADE_SEC) // 2  # クロスフェード分を加味
        print(f"=== 分割生成モード（{duration}秒 → {part_dur}秒 x 2, クロスフェード{CROSSFADE_SEC}秒） ===")

        cap1 = caption
        cap2 = caption2 if caption2 else caption

        with tempfile.TemporaryDirectory() as tmpdir:
            part1_path = os.path.join(tmpdir, "part1.mp3")
            part2_path = os.path.join(tmpdir, "part2.mp3")

            print(f"\n--- Part 1 / 2 ---")
            generate_single(cap1, lyrics, part_dur, part1_path, label="Part 1")

            print(f"\n--- Part 2 / 2 ---")
            generate_single(cap2, lyrics, part_dur, part2_path, label="Part 2")

            print(f"\n--- 結合 ---")
            crossfade_join(part1_path, part2_path, output)

    print(f"\n完了: {output}")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser(
        description="ACE-Step 1.5 で音楽を生成する（30秒超は自動分割+クロスフェード）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--caption", "-c",
        required=True,
        help="音楽スタイルの説明（英語推奨）。分割生成時はPart 1のキャプションとして使用",
    )
    parser.add_argument(
        "--caption2",
        default="",
        help="Part 2用のキャプション（省略時はcaptionと同じ）。前半→後半で雰囲気を変えたい場合に指定",
    )
    parser.add_argument(
        "--lyrics", "-l",
        default="[Instrumental]",
        help="歌詞（インストの場合は '[Instrumental]'、デフォルト）",
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=30,
        help="生成する長さ（秒、デフォルト: 30）。30秒超は自動分割",
    )
    parser.add_argument(
        "--output", "-o",
        default="output_music.mp3",
        help="出力ファイルパス（デフォルト: output_music.mp3）",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"APIサーバーのURL（デフォルト: {BASE_URL}）",
    )

    args = parser.parse_args()

    BASE_URL = args.base_url

    generate_music(
        caption=args.caption,
        caption2=args.caption2,
        lyrics=args.lyrics,
        duration=args.duration,
        output=args.output,
    )


if __name__ == "__main__":
    main()

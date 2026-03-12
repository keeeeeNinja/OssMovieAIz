#!/usr/bin/env python3
"""
ACE-Step 1.5 音楽生成スクリプト
APIサーバー（localhost:8001）に接続して音楽を生成する。

使用前にAPIサーバーを起動してください:
    cd ~/Desktop/Dev/ACE-Step-1.5
    ./start_api_server_macos.sh

使用例:
    python3 scripts/generate_music.py \
        --caption "Calm background music for product advertisement" \
        --duration 30 \
        --output public/bgm.mp3

    python3 scripts/generate_music.py \
        --caption "Upbeat indie pop with jangly guitars" \
        --lyrics "[Verse]\nWalking down the street\n\n[Chorus]\nWe are alive" \
        --duration 30 \
        --output output.mp3
"""

import argparse
import sys
import time
import requests


BASE_URL = "http://localhost:8001"


def check_health():
    try:
        res = requests.get(f"{BASE_URL}/health", timeout=5)
        res.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        return False


def generate_music(caption: str, lyrics: str, duration: int, output: str):
    # ヘルスチェック
    if not check_health():
        print("ERROR: APIサーバーに接続できません。")
        print("以下のコマンドでサーバーを起動してください:")
        print("  cd ~/Desktop/Dev/ACE-Step-1.5")
        print("  ./start_api_server_macos.sh")
        sys.exit(1)

    print(f"[1/3] タスク投入中...")
    print(f"  caption : {caption}")
    print(f"  lyrics  : {lyrics[:50]}..." if len(lyrics) > 50 else f"  lyrics  : {lyrics}")
    print(f"  duration: {duration}秒")

    res = requests.post(f"{BASE_URL}/release_task", json={
        "caption": caption,
        "lyrics": lyrics,
        "duration": duration,
    }, timeout=30)
    res.raise_for_status()
    task_id = res.json()["data"]["task_id"]
    print(f"  task_id : {task_id}")

    # ポーリング（status: 0=実行中, 1=完了, 2=失敗）
    print(f"[2/3] 生成中（ポーリング開始）...")
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

    # ダウンロード
    print(f"[3/3] ダウンロード中: {audio_url}")
    # audio_urlが相対パスの場合はBASE_URLを付ける
    full_url = audio_url if audio_url.startswith("http") else f"{BASE_URL}{audio_url}"
    audio = requests.get(full_url, timeout=60)
    audio.raise_for_status()

    with open(output, "wb") as f:
        f.write(audio.content)

    size_kb = len(audio.content) / 1024
    print(f"  保存完了: {output} ({size_kb:.1f} KB)")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser(
        description="ACE-Step 1.5 で音楽を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--caption", "-c",
        required=True,
        help="音楽スタイルの説明（英語推奨）例: 'Calm background music for product advertisement'",
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
        help="生成する長さ（秒、デフォルト: 30）",
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
        lyrics=args.lyrics,
        duration=args.duration,
        output=args.output,
    )


if __name__ == "__main__":
    main()

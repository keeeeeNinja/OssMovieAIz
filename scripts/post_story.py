#!/usr/bin/env python3
"""
Instagram Stories 自動投稿スクリプト

最新のフィード投稿の画像を取得し、ストーリーズとして投稿する。
Instagram Graph API (Content Publishing API) を使用。

必要な環境変数:
  IG_USER_ID       - Instagram Business Account ID
  IG_ACCESS_TOKEN  - 長期アクセストークン（60日有効）

使い方:
  python3 scripts/post_story.py                    # 最新投稿をストーリーズに投稿
  python3 scripts/post_story.py --dry-run          # 実際には投稿せずに確認
  python3 scripts/post_story.py --post-id 12345    # 特定の投稿をストーリーズに投稿
"""

import argparse
import os
import sys
import time
import urllib.request
import urllib.error
import json

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def api_request(endpoint: str, params: dict | None = None, method: str = "GET") -> dict:
    """Graph API へリクエストを送信する。"""
    url = f"{GRAPH_API_BASE}{endpoint}"
    if method == "GET" and params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
        data = None
    elif method == "POST" and params:
        data = urllib.parse.urlencode(params).encode()
    else:
        data = None

    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"API Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def get_latest_media(ig_user_id: str, access_token: str) -> dict:
    """最新のフィード投稿を取得する。"""
    result = api_request(
        f"/{ig_user_id}/media",
        params={
            "fields": "id,media_type,media_url,thumbnail_url,timestamp,caption",
            "limit": "5",
            "access_token": access_token,
        },
    )
    media_list = result.get("data", [])
    if not media_list:
        print("Error: フィード投稿が見つかりません", file=sys.stderr)
        sys.exit(1)
    return media_list


def get_media_by_id(media_id: str, access_token: str) -> dict:
    """指定IDのメディアを取得する。"""
    return api_request(
        f"/{media_id}",
        params={
            "fields": "id,media_type,media_url,thumbnail_url,timestamp,caption",
            "access_token": access_token,
        },
    )


def create_story_container(ig_user_id: str, image_url: str, access_token: str) -> str:
    """ストーリーズ用のメディアコンテナを作成する。"""
    result = api_request(
        f"/{ig_user_id}/media",
        params={
            "media_type": "STORIES",
            "image_url": image_url,
            "access_token": access_token,
        },
        method="POST",
    )
    container_id = result.get("id")
    if not container_id:
        print(f"Error: コンテナ作成失敗: {result}", file=sys.stderr)
        sys.exit(1)
    return container_id


def publish_container(ig_user_id: str, container_id: str, access_token: str) -> str:
    """コンテナを公開する。"""
    result = api_request(
        f"/{ig_user_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": access_token,
        },
        method="POST",
    )
    media_id = result.get("id")
    if not media_id:
        print(f"Error: 公開失敗: {result}", file=sys.stderr)
        sys.exit(1)
    return media_id


def wait_for_container(container_id: str, access_token: str, max_wait: int = 60) -> None:
    """コンテナのステータスが FINISHED になるまで待機する。"""
    for _ in range(max_wait // 5):
        result = api_request(
            f"/{container_id}",
            params={
                "fields": "status_code",
                "access_token": access_token,
            },
        )
        status = result.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            print(f"Error: コンテナ処理失敗: {result}", file=sys.stderr)
            sys.exit(1)
        print(f"  コンテナ処理中... (status: {status})")
        time.sleep(5)
    print("Error: コンテナ処理タイムアウト", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Instagram Stories 自動投稿")
    parser.add_argument("--dry-run", action="store_true", help="実際には投稿せずに確認のみ")
    parser.add_argument("--post-id", type=str, help="特定の投稿IDを指定")
    args = parser.parse_args()

    ig_user_id = os.environ.get("IG_USER_ID")
    access_token = os.environ.get("IG_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        print("Error: IG_USER_ID と IG_ACCESS_TOKEN 環境変数を設定してください", file=sys.stderr)
        sys.exit(1)

    # 投稿を取得
    if args.post_id:
        media = get_media_by_id(args.post_id, access_token)
        print(f"指定投稿: {media.get('id')} ({media.get('media_type')})")
    else:
        media_list = get_latest_media(ig_user_id, access_token)
        # IMAGE タイプの最新投稿を探す
        media = None
        for m in media_list:
            if m.get("media_type") == "IMAGE":
                media = m
                break
        if not media:
            print("Error: IMAGE タイプのフィード投稿が見つかりません", file=sys.stderr)
            print("直近の投稿:", [f"{m['id']}({m['media_type']})" for m in media_list])
            sys.exit(1)
        print(f"最新画像投稿: {media.get('id')}")

    image_url = media.get("media_url")
    caption = (media.get("caption") or "")[:50]
    print(f"  caption: {caption}...")
    print(f"  media_url: {image_url[:80]}...")

    if args.dry_run:
        print("\n[dry-run] ストーリーズ投稿をスキップしました")
        return

    # ストーリーズ投稿
    print("\nストーリーズ コンテナ作成中...")
    container_id = create_story_container(ig_user_id, image_url, access_token)
    print(f"  container_id: {container_id}")

    print("コンテナ処理待機中...")
    wait_for_container(container_id, access_token)

    print("ストーリーズ公開中...")
    story_id = publish_container(ig_user_id, container_id, access_token)
    print(f"  ストーリーズ投稿完了! story_id: {story_id}")


if __name__ == "__main__":
    main()

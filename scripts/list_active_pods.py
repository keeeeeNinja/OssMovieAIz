#!/usr/bin/env python3
"""現在 RUNNING/STARTING な Pod を一覧表示（オーファン Pod 確認用）"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

for _path in [Path.cwd() / ".env", Path.home() / ".config" / "ossmovie" / ".env"]:
    if _path.exists():
        load_dotenv(_path, override=True)
        break


def get_api_key():
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key:
        try:
            r = subprocess.run(
                ["zsh", "-c", "source ~/.zshrc 2>/dev/null; echo $RUNPOD_API_KEY"],
                capture_output=True, text=True, timeout=5,
            )
            key = r.stdout.strip()
        except Exception:
            pass
    if not key:
        sys.exit("❌ RUNPOD_API_KEY 未設定")
    return key


def main():
    terminate = "--terminate-uploader" in sys.argv
    api_key = get_api_key()
    # REST API は安定。GraphQL myself.pods は 403 を返すケースあり
    req = urllib.request.Request(
        "https://rest.runpod.io/v1/pods",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    pods = json.loads(urllib.request.urlopen(req, timeout=30).read()) or []
    if not pods:
        print("✅ アクティブな Pod なし")
        return
    print(f"アクティブ Pod: {len(pods)} 件")
    for p in pods:
        rt = p.get("runtime") or {}
        up = rt.get("uptimeInSeconds")
        print(f"  {p['id']}  status={p.get('desiredStatus')}  name={p.get('name')}  uptime={up}s")
        if terminate and (p.get("name", "").startswith("vol-uploader-")):
            print(f"    → 削除中: {p['id']}")
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"https://rest.runpod.io/v1/pods/{p['id']}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    method="DELETE",
                ), timeout=30).read()
                print(f"    ✅ 削除完了")
            except Exception as e:
                print(f"    ❌ 削除失敗: {e}")


if __name__ == "__main__":
    main()

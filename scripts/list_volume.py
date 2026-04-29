#!/usr/bin/env python3
"""Volume の指定 prefix 配下のファイル一覧を S3 互換 API で取得"""
import argparse
import os
import sys

from dotenv import load_dotenv
from pathlib import Path

# .env 読み込み優先度: プロジェクトルート → ~/.config/ossmovie/.env → 既存環境変数
_env_candidates = [
    Path.cwd() / ".env",
    Path.home() / ".config" / "ossmovie" / ".env",
]
for _path in _env_candidates:
    if _path.exists():
        load_dotenv(_path, override=True)
        break

# AWS_* 残骸が残っていると boto3 がそちらを優先する事故があるので除去
for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(_k, None)

import boto3
from botocore.config import Config

p = argparse.ArgumentParser()
p.add_argument("prefix", default="ComfyUI/models/", nargs="?",
               help="例: ComfyUI/models/vae/")
args = p.parse_args()

c = boto3.client(
    "s3",
    endpoint_url=os.environ["RUNPOD_S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUNPOD_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUNPOD_S3_SECRET_KEY"],
    region_name=os.environ["RUNPOD_S3_REGION"],  # RunPod は大文字 (EU-RO-1) を使う
)

bucket = os.environ.get("RUNPOD_VOLUME_ID", "c1dbeweh5j")


def fmt_size(n):
    """バイト数を読みやすい単位で。0/小サイズも判別したいので 1KB 未満はバイト表示。"""
    if n < 1024:
        return f"{n:>8d}  B"
    if n < 1024 * 1024:
        return f"{n/1024:>8.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n/1024/1024:>8.1f} MB"
    return f"{n/1024/1024/1024:>8.2f} GB"


prefix = args.prefix
# RunPod S3 のクセ: Delimiter なしの list_objects_v2 が KeyCount=0,
# IsTruncated=True を返すケースがある。Delimiter='/' を必ず指定する。
total_files = 0
total_dirs = 0
continuation = None
seen_tokens = set()
for _ in range(100):
    kwargs = dict(Bucket=bucket, Prefix=prefix, Delimiter="/", MaxKeys=1000)
    if continuation:
        kwargs["ContinuationToken"] = continuation
    resp = c.list_objects_v2(**kwargs)
    for p in resp.get("CommonPrefixes", []):
        print(f"  {'<DIR>':>11}  {p['Prefix']}")
        total_dirs += 1
    for obj in resp.get("Contents", []):
        print(f"  {fmt_size(obj['Size'])}  {obj['Key']}")
        total_files += 1
    if not resp.get("IsTruncated"):
        break
    next_token = resp.get("NextContinuationToken")
    if not next_token or next_token in seen_tokens:
        break
    seen_tokens.add(next_token)
    continuation = next_token

print(f"\n合計 ファイル {total_files} / ディレクトリ {total_dirs}")

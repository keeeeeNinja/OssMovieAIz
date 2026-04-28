#!/usr/bin/env python3
"""
RunPod Network Volume から S3 互換 API でファイルを取得する。

前提環境変数:
  RUNPOD_S3_ENDPOINT     例: https://s3api-eu-ro-1.runpod.io
  RUNPOD_S3_ACCESS_KEY
  RUNPOD_S3_SECRET_KEY
  RUNPOD_VOLUME_ID       例: c1dbeweh5j
  RUNPOD_S3_REGION       例: EU-RO-1（省略可）

Usage:
  # job_map_flux.json に基づいて全 job を取得
  python3 scripts/serverless_fetch.py \\
    --endpoint flux \\
    --output-root 作業中動画

  # 特定 job_id だけ
  python3 scripts/serverless_fetch.py \\
    --job-id <job_id> \\
    --remote-prefix outputs/images/<job_id>/ \\
    --dest 作業中動画/theme1
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv(override=True)

# AWS_* 残骸が残っていると boto3 がそちらを優先する事故があるので除去
for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(_k, None)

try:
    import boto3
    from botocore.config import Config
except ImportError:
    sys.exit("boto3 が必要です: pip install boto3")


def get_s3_client():
    endpoint = os.environ.get("RUNPOD_S3_ENDPOINT", "")
    access_key = os.environ.get("RUNPOD_S3_ACCESS_KEY", "")
    secret_key = os.environ.get("RUNPOD_S3_SECRET_KEY", "")
    region = os.environ.get("RUNPOD_S3_REGION", "EU-RO-1")
    missing = [k for k, v in {
        "RUNPOD_S3_ENDPOINT": endpoint,
        "RUNPOD_S3_ACCESS_KEY": access_key,
        "RUNPOD_S3_SECRET_KEY": secret_key,
    }.items() if not v]
    if missing:
        sys.exit(f"環境変数が未設定: {', '.join(missing)}")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,  # RunPod は大文字 (EU-RO-1) を使う
    )


def fetch_prefix(client, bucket, prefix, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    paginator = client.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = os.path.basename(key)
            if not filename:
                continue
            local_path = os.path.join(dest_dir, filename)
            print(f"  ↓ {key} → {local_path}")
            client.download_file(bucket, key, local_path)
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--volume-id", default=os.environ.get("RUNPOD_VOLUME_ID", ""))
    parser.add_argument("--output-root", default="作業中動画")
    parser.add_argument("--endpoint", choices=["flux", "i2v"],
                        help="job_map_{endpoint}.json に基づいて全件取得")
    parser.add_argument("--job-id", default="", help="特定 job_id だけ")
    parser.add_argument("--remote-prefix", default="",
                        help="--job-id のとき Volume 上のプレフィックス (例: outputs/images/<job_id>/)")
    parser.add_argument("--dest", default="", help="--job-id のとき保存先ディレクトリ")
    args = parser.parse_args()

    if not args.volume_id:
        sys.exit("--volume-id か環境変数 RUNPOD_VOLUME_ID を設定してください")

    client = get_s3_client()

    if args.job_id:
        prefix = args.remote_prefix or f"outputs/images/{args.job_id}/"
        dest = args.dest or args.output_root
        n = fetch_prefix(client, args.volume_id, prefix, dest)
        print(f"\n取得: {n} ファイル → {dest}")
        return

    if not args.endpoint:
        sys.exit("--endpoint または --job-id を指定してください")

    job_map_path = os.path.join(args.output_root, f"job_map_{args.endpoint}.json")
    if not os.path.exists(job_map_path):
        sys.exit(f"job map が見つかりません: {job_map_path}")
    with open(job_map_path) as f:
        jobs = json.load(f)

    sub = "images" if args.endpoint == "flux" else "videos"
    total = 0
    for job in jobs:
        prefix = f"outputs/{sub}/{job['job_id']}/"
        dest = job.get("theme_dir") or args.output_root
        n = fetch_prefix(client, args.volume_id, prefix, dest)
        total += n
    print(f"\n取得完了: {total} ファイル")


if __name__ == "__main__":
    main()

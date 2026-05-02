#!/usr/bin/env python3
"""Network Volume へファイルを S3 互換 API でアップロード。
multipart 自動。進捗バーは boto3 Callback で表示。

Usage:
  python3 scripts/upload_volume.py /tmp/flux1-schnell-Q8_0.gguf ComfyUI/models/unet/flux1-schnell-Q8_0.gguf
"""
import argparse
import os
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path.cwd() / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(_k, None)

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config


class Progress:
    def __init__(self, total):
        self.total = total
        self.seen = 0
        self.start = time.time()
        self.lock = threading.Lock()

    def __call__(self, n):
        with self.lock:
            self.seen += n
            pct = self.seen * 100.0 / self.total if self.total else 0
            elapsed = time.time() - self.start
            rate = self.seen / elapsed if elapsed > 0 else 0
            mb = self.seen / (1024 * 1024)
            tot_mb = self.total / (1024 * 1024)
            sys.stdout.write(
                f"\r  {mb:>8.1f} / {tot_mb:.1f} MB  ({pct:5.1f}%)  {rate/1024/1024:5.1f} MB/s"
            )
            sys.stdout.flush()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("local")
    p.add_argument("key")
    p.add_argument("--bucket", default=os.environ.get("RUNPOD_VOLUME_ID", ""))
    args = p.parse_args()

    if not args.bucket:
        sys.exit("❌ RUNPOD_VOLUME_ID を .env に設定するか --bucket を指定してください")

    if not os.path.isfile(args.local):
        sys.exit(f"❌ ローカルファイルなし: {args.local}")

    size = os.path.getsize(args.local)
    print(f"📤 {args.local} ({size/1024/1024/1024:.2f} GB) → s3://{args.bucket}/{args.key}")

    boto_cfg = Config(
        connect_timeout=60,
        read_timeout=300,
        retries={"max_attempts": 10, "mode": "adaptive"},
        max_pool_connections=20,
    )
    c = boto3.client(
        "s3",
        endpoint_url=os.environ["RUNPOD_S3_ENDPOINT"],
        aws_access_key_id=os.environ["RUNPOD_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["RUNPOD_S3_SECRET_KEY"],
        region_name=os.environ["RUNPOD_S3_REGION"],
        config=boto_cfg,
    )

    cfg = TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        multipart_chunksize=64 * 1024 * 1024,
        max_concurrency=8,
        use_threads=True,
    )

    cb = Progress(size)
    c.upload_file(args.local, args.bucket, args.key, Config=cfg, Callback=cb)
    print(f"\n✅ アップロード完了")


if __name__ == "__main__":
    main()

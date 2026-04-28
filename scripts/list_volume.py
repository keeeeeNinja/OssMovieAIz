#!/usr/bin/env python3
"""Volume の指定 prefix 配下のファイル一覧を S3 互換 API で取得"""
import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv(override=True)

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

paginator = c.get_paginator("list_objects_v2")
total = 0
for page in paginator.paginate(Bucket="c1dbeweh5j", Prefix=args.prefix):
    for obj in page.get("Contents", []):
        size_mb = obj["Size"] / (1024 * 1024)
        print(f"{size_mb:>10.1f} MB  {obj['Key']}")
        total += 1
print(f"\n合計 {total} ファイル")

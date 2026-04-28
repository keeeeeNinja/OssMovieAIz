#!/usr/bin/env python3
"""Volume 内で t5xxl_fp8_e4m3fn.safetensors を models/clip/ から models/text_encoders/ にサーバーサイドコピー。
Flux ワークフローが text_encoders/ を見るための一時的な対応。"""
import os

from dotenv import load_dotenv
load_dotenv(override=True)

# AWS_* 残骸が残っていると boto3 がそちらを優先する事故があるので除去
for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(_k, None)

import boto3
from botocore.config import Config

c = boto3.client(
    "s3",
    endpoint_url=os.environ["RUNPOD_S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUNPOD_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUNPOD_S3_SECRET_KEY"],
    region_name=os.environ["RUNPOD_S3_REGION"],  # RunPod は大文字
)

bucket = "c1dbeweh5j"
src_key = "ComfyUI/models/clip/t5xxl_fp8_e4m3fn.safetensors"
dst_key = "ComfyUI/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors"

print(f"copy {src_key} -> {dst_key} (server-side)...")
c.copy_object(Bucket=bucket, Key=dst_key, CopySource={"Bucket": bucket, "Key": src_key})
print("copied")

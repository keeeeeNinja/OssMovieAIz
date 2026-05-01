#!/usr/bin/env python3
"""Volume から Flux Dev 派生資産を一括削除（商用利用対応の最終クリーンアップ）。"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

for _path in [Path.cwd() / ".env", Path.home() / ".config" / "ossmovie" / ".env"]:
    if _path.exists():
        load_dotenv(_path, override=True)
        break

for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(_k, None)

import boto3

c = boto3.client(
    "s3",
    endpoint_url=os.environ["RUNPOD_S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUNPOD_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUNPOD_S3_SECRET_KEY"],
    region_name=os.environ["RUNPOD_S3_REGION"],
)
bucket = os.environ.get("RUNPOD_VOLUME_ID", "c1dbeweh5j")

TARGETS = [
    "ComfyUI/models/unet/flux1-dev.safetensors",
    "ComfyUI/models/unet/flux1-kontext-dev-Q8_0.gguf",
    "ComfyUI/models/loras/URDP001_v2.safetensors",
    "ComfyUI/models/loras/ayano_chan_flux_lora-step00001000.safetensors",
    "ComfyUI/models/loras/ayano_chan_flux_lora-step00001400.safetensors",
    "ComfyUI/models/loras/ayano_chan_flux_lora-step00001800.safetensors",
    "ComfyUI/models/loras/ayano_chan_flux_lora-step00002000.safetensors",
    "ComfyUI/models/loras/flux_japanese_girl_v2.safetensors",
    "ComfyUI/models/loras/rin_chan_v1.safetensors",
    "ComfyUI/models/loras/sawayaka_men_v1.safetensors",
]

freed = 0
for key in TARGETS:
    try:
        meta = c.head_object(Bucket=bucket, Key=key)
        size = meta["ContentLength"]
    except Exception:
        print(f"  ⏭️  {key} (not found)")
        continue
    c.delete_object(Bucket=bucket, Key=key)
    freed += size
    print(f"  🗑️  {key} ({size/1024/1024:.1f} MB)")

print(f"\n✅ 削除完了: {freed/1024/1024/1024:.2f} GB 解放")

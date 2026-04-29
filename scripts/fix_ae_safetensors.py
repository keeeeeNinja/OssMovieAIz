#!/usr/bin/env python3
"""
Volume 上の壊れた ae.safetensors を HF_TOKEN 経由で再ダウンロードして上書きする。

前提:
- ~/.zshrc に HF_TOKEN（gated アクセス権限あり）
- .env に S3 認証情報

使い方:
  zsh -c 'source ~/.zshrc; python scripts/fix_ae_safetensors.py'
"""
import os
import sys
import time
import urllib.request
import urllib.error

from dotenv import load_dotenv
load_dotenv(override=True)

# AWS_* 残骸が残っていると boto3 がそちらを優先するので除去
for _k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(_k, None)

import boto3

HF_URL = "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors"
LOCAL_PATH = "/tmp/ae_safetensors_dl"
BUCKET = os.environ.get("RUNPOD_VOLUME_ID", "c1dbeweh5j")
KEY = "ComfyUI/models/vae/ae.safetensors"
EXPECTED_MIN_BYTES = 300_000_000  # 約 330MB を期待。300MB 未満なら失敗扱い

hf_token = os.environ.get("HF_TOKEN", "")
if not hf_token:
    sys.exit("❌ HF_TOKEN が設定されていません（~/.zshrc 確認）")

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["RUNPOD_S3_ENDPOINT"],
    aws_access_key_id=os.environ["RUNPOD_S3_ACCESS_KEY"],
    aws_secret_access_key=os.environ["RUNPOD_S3_SECRET_KEY"],
    region_name=os.environ["RUNPOD_S3_REGION"],
)


def step(label):
    print(f"\n=== {label} ===", flush=True)


# Step 1: 既存ファイルのサイズ確認
step("Step 1: 既存 ae.safetensors のサイズ確認")
try:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=KEY, Delimiter="/")
    found = False
    for obj in resp.get("Contents", []):
        if obj["Key"] == KEY:
            print(f"  現状: {obj['Size']} bytes")
            found = True
            if obj["Size"] >= EXPECTED_MIN_BYTES:
                print("  すでに正常サイズです。スキップします。")
                sys.exit(0)
    if not found:
        print("  Volume 上に存在しません（新規作成）")
except Exception as e:
    print(f"  サイズ確認エラー (続行): {e}")

# Step 2: 既存の壊れたファイルを削除
step("Step 2: 既存ファイル削除")
try:
    s3.delete_object(Bucket=BUCKET, Key=KEY)
    print("  削除完了")
except Exception as e:
    print(f"  削除エラー (続行): {e}")

# Step 3: HF から認証付きダウンロード
step("Step 3: HuggingFace から認証付きダウンロード")
print(f"  URL: {HF_URL}")
print(f"  Local: {LOCAL_PATH}")

req = urllib.request.Request(HF_URL, headers={"Authorization": f"Bearer {hf_token}"})
t0 = time.time()
total = 0
chunk_size = 1024 * 1024  # 1 MB
with urllib.request.urlopen(req, timeout=60) as response:
    expected = response.headers.get("Content-Length")
    if expected:
        expected = int(expected)
        print(f"  Content-Length: {expected} bytes ({expected/1024/1024:.1f} MB)")
    with open(LOCAL_PATH, "wb") as f:
        last_print = 0
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            now = time.time()
            if now - last_print > 2:
                mb = total / 1024 / 1024
                speed = total / (now - t0) / 1024 / 1024
                print(f"  ↓ {mb:.1f} MB ({speed:.1f} MB/s)", flush=True)
                last_print = now

elapsed = time.time() - t0
size_mb = total / 1024 / 1024
print(f"  ✅ DL 完了: {total} bytes ({size_mb:.1f} MB) in {elapsed:.1f}s ({size_mb/elapsed:.1f} MB/s)")

if total < EXPECTED_MIN_BYTES:
    sys.exit(f"❌ ダウンロードサイズ異常: {total} bytes（期待 >{EXPECTED_MIN_BYTES}）。HF_TOKEN の権限を確認してください。")

# Step 4: Volume へアップロード
step("Step 4: S3 経由で Volume へアップロード")
t0 = time.time()
last_print = [t0, 0]


def progress(bytes_amount):
    last_print[1] += bytes_amount
    now = time.time()
    if now - last_print[0] > 2:
        mb = last_print[1] / 1024 / 1024
        speed = last_print[1] / (now - t0) / 1024 / 1024
        print(f"  ↑ {mb:.1f} MB ({speed:.1f} MB/s)", flush=True)
        last_print[0] = now


s3.upload_file(LOCAL_PATH, BUCKET, KEY, Callback=progress)
elapsed = time.time() - t0
print(f"  ✅ Upload 完了 in {elapsed:.1f}s ({(total/1024/1024)/elapsed:.1f} MB/s)")

# Step 5: 検証
step("Step 5: アップロード後のサイズ確認")
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=KEY, Delimiter="/")
for obj in resp.get("Contents", []):
    if obj["Key"] == KEY:
        if obj["Size"] == total:
            print(f"  ✅ 一致: {obj['Size']} bytes")
        else:
            print(f"  ⚠️  サイズ不一致: Volume {obj['Size']} vs DL {total}")

# Step 6: クリーンアップ
step("Step 6: ローカル一時ファイル削除")
try:
    os.unlink(LOCAL_PATH)
    print(f"  削除: {LOCAL_PATH}")
except Exception:
    pass

print("\n🎉 ae.safetensors 修復完了")

#!/usr/bin/env python3
"""
RunPod Serverless Endpoint 作成スクリプト (Flux 用 / Wan I2V 用)。

前提:
  - docker/Dockerfile.serverless が GitHub Actions でビルドされ、
    レジストリ（GHCR など）に push 済み
  - Network Volume `c1dbeweh5j` が EU-RO-1 にある（既存）
  - 環境変数 RUNPOD_API_KEY が設定されている
  - GHCR が private の場合は RunPod 側で「Container Registry Auth」を作成し
    その ID を --registry-auth-id で指定する（public なら不要）

Usage:
  # 両方作成（推奨）
  python3 scripts/create_serverless_endpoint.py \\
    --image ghcr.io/keeeeeninja/ossmovie-comfyui:latest \\
    --volume-id c1dbeweh5j \\
    --datacenter EU-RO-1 \\
    --kind both

  # Flux だけ
  python3 scripts/create_serverless_endpoint.py --kind flux ...

  # 作成後、表示される Endpoint ID を ~/.config/ossmovie/.env に追記:
  #   RUNPOD_ENDPOINT_FLUX=...
  #   RUNPOD_ENDPOINT_I2V=...
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

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

REST_BASE = "https://rest.runpod.io/v1"


def get_api_key():
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key:
        try:
            result = subprocess.run(
                ["zsh", "-c", "source ~/.zshrc 2>/dev/null; echo $RUNPOD_API_KEY"],
                capture_output=True, text=True, timeout=5,
            )
            key = result.stdout.strip()
        except Exception:
            pass
    if not key:
        sys.exit("❌ RUNPOD_API_KEY が設定されていません")
    return key


def rest_post(api_key, path, body):
    req = urllib.request.Request(
        f"{REST_BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        sys.exit(f"❌ HTTP {e.code} {path}: {body_txt}")


def create_template(api_key, name, image, registry_auth_id=None):
    body = {
        "name": name,
        "imageName": image,
        "isServerless": True,
        "containerDiskInGb": 20,
        "volumeInGb": 0,
        "readme": "OssMovieAIz Serverless ComfyUI worker (auto-generated).",
        "env": {"COMFY_OUTPUT_PATH": "/runpod-volume/outputs"},
    }
    if registry_auth_id:
        body["containerRegistryAuthId"] = registry_auth_id
    data = rest_post(api_key, "/templates", body)
    template_id = data.get("id")
    if not template_id:
        sys.exit(f"❌ Template 作成 response 異常: {data}")
    print(f"✅ Template 作成: {template_id} ({name})")
    return template_id


def create_endpoint(api_key, name, template_id, volume_id, datacenter, gpu_type_ids,
                    workers_min, workers_max, idle_timeout, exec_timeout_ms):
    body = {
        "name": name,
        "templateId": template_id,
        "computeType": "GPU",
        "gpuTypeIds": gpu_type_ids,
        "gpuCount": 1,
        "networkVolumeId": volume_id,
        "dataCenterIds": [datacenter],
        "workersMin": workers_min,
        "workersMax": workers_max,
        "idleTimeout": idle_timeout,
        "executionTimeoutMs": exec_timeout_ms,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "flashboot": True,
    }
    data = rest_post(api_key, "/endpoints", body)
    endpoint_id = data.get("id")
    if not endpoint_id:
        sys.exit(f"❌ Endpoint 作成 response 異常: {data}")
    print(f"✅ Endpoint 作成: {endpoint_id} ({name})")
    return endpoint_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image",
                        default=os.environ.get("SERVERLESS_IMAGE", ""),
                        help="Docker image 名（未指定なら環境変数 SERVERLESS_IMAGE を使う）")
    parser.add_argument("--volume-id",
                        default=os.environ.get("RUNPOD_VOLUME_ID", "c1dbeweh5j"))
    parser.add_argument("--datacenter", default="EU-RO-1")
    parser.add_argument("--kind", choices=["flux", "i2v", "both"], default="both")
    parser.add_argument("--gpu-ids",
                        default="NVIDIA GeForce RTX 4090,NVIDIA GeForce RTX 5090",
                        help="プライオリティ順カンマ区切り（REST では gpuTypeIds の配列に変換）")
    parser.add_argument("--workers-min", type=int, default=0)
    parser.add_argument("--workers-max", type=int, default=3)
    parser.add_argument("--idle-timeout", type=int, default=5,
                        help="アイドル中の秒数（デフォルト 5 秒、コールドスタート最小化なら大きく）")
    parser.add_argument("--registry-auth-id", default="",
                        help="GHCR が private の場合 RunPod に登録した Container Registry Auth の ID")
    args = parser.parse_args()

    if not args.image:
        sys.exit("❌ --image または環境変数 SERVERLESS_IMAGE を指定してください")

    api_key = get_api_key()

    targets = []
    if args.kind in ("flux", "both"):
        targets.append(("ossmovie-flux", 600_000))
    if args.kind in ("i2v", "both"):
        targets.append(("ossmovie-i2v", 900_000))

    gpu_type_ids = [s.strip() for s in args.gpu_ids.split(",") if s.strip()]

    results = {}
    for name, exec_ms in targets:
        template_id = create_template(api_key, name, args.image,
                                      registry_auth_id=args.registry_auth_id or None)
        endpoint_id = create_endpoint(
            api_key, name, template_id, args.volume_id, args.datacenter,
            gpu_type_ids, args.workers_min, args.workers_max,
            args.idle_timeout, exec_ms,
        )
        results[name] = endpoint_id

    print("\n=== 完了 ===")
    for name, eid in results.items():
        print(f"  {name}: {eid}")
    print("\n~/.config/ossmovie/.env に以下を追記してください:")
    if "ossmovie-flux" in results:
        print(f'  RUNPOD_ENDPOINT_FLUX={results["ossmovie-flux"]}')
    if "ossmovie-i2v" in results:
        print(f'  RUNPOD_ENDPOINT_I2V={results["ossmovie-i2v"]}')


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
RunPod Serverless Endpoint 作成スクリプト (Flux 用 / Wan I2V 用)。

前提:
  - docker/Dockerfile.serverless が GitHub Actions でビルドされ、
    レジストリ（GHCR など）に push 済み
  - Network Volume を EU-RO-1 に作成済み（受講者は自分で作成）
  - 環境変数 RUNPOD_API_KEY が設定されている
  - GHCR が private の場合は RunPod 側で「Container Registry Auth」を作成し
    その ID を --registry-auth-id で指定する（public なら不要）

Usage:
  # .env に RUNPOD_VOLUME_ID と RUNPOD_API_KEY を設定後、以下のみで OK:
  python3 scripts/create_serverless_endpoint.py --kind all

  # 個別に Endpoint だけ作りたい場合
  python3 scripts/create_serverless_endpoint.py --kind flux

  # 作成後、表示される Endpoint ID を .env に追記:
  #   RUNPOD_ENDPOINT_FLUX=...
  #   RUNPOD_ENDPOINT_I2V=...
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv
from pathlib import Path

_env_path = Path.cwd() / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

REST_BASE = "https://rest.runpod.io/v1"


def get_api_key():
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key:
        sys.exit("❌ RUNPOD_API_KEY が .env に設定されていません")
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


def create_template(api_key, name, image, registry_auth_id=None, kind="comfyui"):
    """kind=comfyui (flux/i2v) / tts (Qwen3-TTS) / acestep (ACE-Step XL) を切り替え。env 変数が違う。"""
    if kind == "tts":
        env = {
            "HF_HOME": "/runpod-volume/hf_cache",
            "HUGGINGFACE_HUB_CACHE": "/runpod-volume/hf_cache",
        }
        readme = "OssMovieAIz Serverless Qwen3-TTS worker (auto-generated)."
        disk = 30  # PyTorch + flash-attn + qwen-tts deps が太い
    elif kind == "acestep":
        env = {
            "HF_HOME": "/runpod-volume/hf_cache",
            "HUGGINGFACE_HUB_CACHE": "/runpod-volume/hf_cache",
        }
        readme = "OssMovieAIz Serverless ACE-Step XL BGM worker (auto-generated)."
        disk = 40  # torch 2.10 + ACE-Step + flash-attn + nano-vllm が太い
    else:
        env = {"COMFY_OUTPUT_PATH": "/runpod-volume/outputs"}
        readme = "OssMovieAIz Serverless ComfyUI worker (auto-generated)."
        disk = 20
    body = {
        "name": name,
        "imageName": image,
        "isServerless": True,
        "containerDiskInGb": disk,
        "volumeInGb": 0,
        "readme": readme,
        "env": env,
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
                        help="ComfyUI worker の Docker image（flux/i2v 用、env SERVERLESS_IMAGE）")
    parser.add_argument("--tts-image",
                        default=os.environ.get("SERVERLESS_TTS_IMAGE",
                                                "ghcr.io/keeeeeninja/ossmovie-tts:latest"),
                        help="TTS worker の Docker image（tts 用、env SERVERLESS_TTS_IMAGE）")
    parser.add_argument("--acestep-image",
                        default=os.environ.get("SERVERLESS_ACESTEP_IMAGE",
                                                "ghcr.io/keeeeeninja/ossmovie-acestep:latest"),
                        help="ACE-Step worker の Docker image（acestep 用、env SERVERLESS_ACESTEP_IMAGE）")
    parser.add_argument("--volume-id",
                        default=os.environ.get("RUNPOD_VOLUME_ID", ""))
    parser.add_argument("--datacenter", default=os.environ.get("RUNPOD_DATACENTER", "EU-RO-1"))
    parser.add_argument("--kind", choices=["flux", "i2v", "tts", "acestep", "all"], default="all")
    parser.add_argument("--gpu-ids",
                        default="NVIDIA GeForce RTX 4090,NVIDIA GeForce RTX 5090",
                        help="プライオリティ順カンマ区切り（REST では gpuTypeIds の配列に変換）")
    parser.add_argument("--workers-min", type=int, default=0)
    parser.add_argument("--workers-max", type=int, default=3)
    parser.add_argument("--idle-timeout", type=int, default=120,
                        help="アイドル中の秒数（デフォルト 120 秒。連続生成中の Worker 維持で再ロード回避）")
    parser.add_argument("--registry-auth-id", default="",
                        help="GHCR が private の場合 RunPod に登録した Container Registry Auth の ID")
    parser.add_argument("--name-suffix", default="",
                        help="Template/Endpoint 名のサフィックス（例: -us-ca-2）。空だと付かない")
    args = parser.parse_args()

    if not args.volume_id:
        sys.exit("❌ RUNPOD_VOLUME_ID を .env に設定するか --volume-id を指定してください")

    api_key = get_api_key()

    sfx = args.name_suffix
    # (name, exec_timeout_ms, image, kind) の順
    targets = []
    if args.kind in ("flux", "all"):
        if not args.image:
            sys.exit("❌ flux 作成には --image または env SERVERLESS_IMAGE が必要")
        targets.append((f"ossmovie-flux{sfx}", 600_000, args.image, "comfyui"))
    if args.kind in ("i2v", "all"):
        if not args.image:
            sys.exit("❌ i2v 作成には --image または env SERVERLESS_IMAGE が必要")
        # Wan 2.1 14B はコールドスタート（イメージ pull + 10GB+ ロード）込みで 15〜25 分要するため 30 分余裕
        targets.append((f"ossmovie-i2v{sfx}", 1_800_000, args.image, "comfyui"))
    if args.kind in ("tts", "all"):
        if not args.tts_image:
            sys.exit("❌ tts 作成には --tts-image または env SERVERLESS_TTS_IMAGE が必要")
        targets.append((f"ossmovie-tts{sfx}", 120_000, args.tts_image, "tts"))
    if args.kind in ("acestep", "all"):
        if not args.acestep_image:
            sys.exit("❌ acestep 作成には --acestep-image または env SERVERLESS_ACESTEP_IMAGE が必要")
        # ACE-Step XL Turbo は60秒生成で1〜2分。分割で計2回投入されることもあるので余裕を持たせる
        targets.append((f"ossmovie-acestep{sfx}", 600_000, args.acestep_image, "acestep"))

    gpu_type_ids = [s.strip() for s in args.gpu_ids.split(",") if s.strip()]

    results = {}
    for name, exec_ms, image, kind in targets:
        template_id = create_template(api_key, name, image,
                                      registry_auth_id=args.registry_auth_id or None,
                                      kind=kind)
        endpoint_id = create_endpoint(
            api_key, name, template_id, args.volume_id, args.datacenter,
            gpu_type_ids, args.workers_min, args.workers_max,
            args.idle_timeout, exec_ms,
        )
        results[name] = endpoint_id

    print("\n=== 完了 ===")
    for name, eid in results.items():
        print(f"  {name}: {eid}")
    print("\n.env に以下を追記してください:")
    if "ossmovie-flux" in results:
        print(f'  RUNPOD_ENDPOINT_FLUX={results["ossmovie-flux"]}')
    if "ossmovie-i2v" in results:
        print(f'  RUNPOD_ENDPOINT_I2V={results["ossmovie-i2v"]}')
    if "ossmovie-tts" in results:
        print(f'  RUNPOD_ENDPOINT_TTS={results["ossmovie-tts"]}')
    if "ossmovie-acestep" in results:
        print(f'  RUNPOD_ENDPOINT_ACESTEP={results["ossmovie-acestep"]}')


if __name__ == "__main__":
    main()

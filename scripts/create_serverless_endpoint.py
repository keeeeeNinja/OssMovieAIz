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

  # 作成後、表示される Endpoint ID を ~/.zshrc に追加:
  #   export RUNPOD_ENDPOINT_FLUX=...
  #   export RUNPOD_ENDPOINT_I2V=...
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request

RUNPOD_API_URL = "https://api.runpod.io/graphql"


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


def runpod_query(api_key, query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    req = urllib.request.Request(
        RUNPOD_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Template (Docker image + container 設定) を作る
TEMPLATE_MUTATION = """
mutation saveTemplate($input: SaveTemplateInput!) {
  saveTemplate(input: $input) {
    id
    name
  }
}
"""

# Template を参照して Endpoint を作る
ENDPOINT_MUTATION = """
mutation saveEndpoint($input: EndpointInput!) {
  saveEndpoint(input: $input) {
    id
    name
    templateId
    gpuIds
  }
}
"""


def create_template(api_key, name, image, registry_auth_id=None):
    template_input = {
        "name": name,
        "imageName": image,
        "containerDiskInGb": 20,
        "volumeInGb": 0,
        "isServerless": True,
        "readme": "OssMovieAIz Serverless ComfyUI worker (auto-generated).",
        # 公式 worker-comfyui のエントリポイントは /start.sh (handler 起動)
        # COMFYUI_OUTPUT_PATH 等の環境変数で出力先を上書きしたい場合は env に追加
        "env": [
            {"key": "COMFY_OUTPUT_PATH", "value": "/runpod-volume/outputs"},
        ],
    }
    if registry_auth_id:
        template_input["containerRegistryAuthId"] = registry_auth_id
    resp = runpod_query(api_key, TEMPLATE_MUTATION, {"input": template_input})
    if "errors" in resp:
        sys.exit(f"❌ Template 作成失敗: {resp['errors']}")
    template_id = resp["data"]["saveTemplate"]["id"]
    print(f"✅ Template 作成: {template_id} ({name})")
    return template_id


def create_endpoint(api_key, name, template_id, volume_id, datacenter, gpu_ids,
                    workers_min, workers_max, idle_timeout, exec_timeout_ms):
    endpoint_input = {
        "name": name,
        "templateId": template_id,
        "gpuIds": gpu_ids,                  # 例: "NVIDIA GeForce RTX 4090,NVIDIA GeForce RTX 5090"
        "networkVolumeId": volume_id,
        "locations": datacenter,            # 例: "EU-RO-1"
        "workersMin": workers_min,
        "workersMax": workers_max,
        "idleTimeout": idle_timeout,        # 秒
        "executionTimeoutMs": exec_timeout_ms,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
    }
    resp = runpod_query(api_key, ENDPOINT_MUTATION, {"input": endpoint_input})
    if "errors" in resp:
        sys.exit(f"❌ Endpoint 作成失敗: {resp['errors']}")
    data = resp["data"]["saveEndpoint"]
    print(f"✅ Endpoint 作成: {data['id']} ({name})")
    return data["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Docker image 名（タグ込み）")
    parser.add_argument("--volume-id", default="c1dbeweh5j")
    parser.add_argument("--datacenter", default="EU-RO-1")
    parser.add_argument("--kind", choices=["flux", "i2v", "both"], default="both")
    parser.add_argument("--gpu-ids",
                        default="NVIDIA GeForce RTX 4090,NVIDIA GeForce RTX 5090",
                        help="プライオリティ順カンマ区切り")
    parser.add_argument("--workers-min", type=int, default=0)
    parser.add_argument("--workers-max", type=int, default=3)
    parser.add_argument("--idle-timeout", type=int, default=5,
                        help="アイドル中の秒数（デフォルト 5 秒、コールドスタート最小化なら大きく）")
    parser.add_argument("--registry-auth-id", default="",
                        help="GHCR が private の場合 RunPod に登録した Container Registry Auth の ID")
    args = parser.parse_args()

    api_key = get_api_key()

    targets = []
    if args.kind in ("flux", "both"):
        targets.append(("ossmovie-flux", 600_000))
    if args.kind in ("i2v", "both"):
        targets.append(("ossmovie-i2v", 900_000))

    results = {}
    for name, exec_ms in targets:
        template_id = create_template(api_key, name, args.image,
                                      registry_auth_id=args.registry_auth_id or None)
        endpoint_id = create_endpoint(
            api_key, name, template_id, args.volume_id, args.datacenter,
            args.gpu_ids, args.workers_min, args.workers_max,
            args.idle_timeout, exec_ms,
        )
        results[name] = endpoint_id

    print("\n=== 完了 ===")
    for name, eid in results.items():
        print(f"  {name}: {eid}")
    print("\n~/.zshrc に以下を追加してください:")
    if "ossmovie-flux" in results:
        print(f'  export RUNPOD_ENDPOINT_FLUX="{results["ossmovie-flux"]}"')
    if "ossmovie-i2v" in results:
        print(f'  export RUNPOD_ENDPOINT_I2V="{results["ossmovie-i2v"]}"')


if __name__ == "__main__":
    main()

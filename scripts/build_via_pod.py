#!/usr/bin/env python3
"""ACE-Step 用 Docker イメージを RunPod Pod 上で buildah ビルドして GHCR に push する。

GitHub Actions ランナー（CPU 4core, 帯域 ~50MB/s）では ACE-Step の重い依存（torch 2.10
+cu128, diffusers, librosa）pull に 1〜2 時間かかってタイムアウト級になるため、
Pod 上で buildah によるデーモンレスビルドに移行する。

前提:
  - 環境変数 RUNPOD_API_KEY（.env に設定）
  - 環境変数 GHCR_PAT（GitHub Personal Access Token, write:packages 権限）
  - SSH 鍵 ~/.ssh/id_ed25519 が RunPod に登録済み

Usage:
  python3 scripts/build_via_pod.py
  # オプション:
  #   --image-tag ghcr.io/keeeeeninja/ossmovie-acestep:custom  （タグ上書き）
  #   --keep-pod                                              （デバッグ用）
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path.cwd() / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

GRAPHQL = "https://api.runpod.io/graphql"
REST_BASE = "https://rest.runpod.io/v1"
SSH_KEY = os.path.expanduser(os.environ.get("RUNPOD_SSH_KEY", "~/.ssh/id_ed25519"))
DATACENTER = os.environ.get("RUNPOD_DATACENTER", "EU-RO-1")
GPU_CANDIDATES = [
    "NVIDIA RTX A4000",       # 最安: $0.17/hr (build には GPU 不要だが Pod 仕様上必須)
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA GeForce RTX 5090",
]
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
REPO_URL = "https://github.com/keeeeeNinja/OssMovieAIz.git"
DEFAULT_TAG = "ghcr.io/keeeeeninja/ossmovie-acestep:latest"


def get_env(name):
    v = os.environ.get(name, "")
    if not v:
        sys.exit(f"❌ {name} が .env に設定されていません")
    return v


def rest_post(api_key, path, body):
    req = urllib.request.Request(
        f"{REST_BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {path}: {body_txt}")


def rest_delete(api_key, path):
    req = urllib.request.Request(
        f"{REST_BASE}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        method="DELETE",
    )
    urllib.request.urlopen(req, timeout=30).read()


def gql(api_key, query):
    req = urllib.request.Request(
        GRAPHQL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "RunPod-Client/1.0",
        },
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def create_pod(api_key, name):
    """build 用 Pod 作成。Network Volume は不要（イメージビルドに使わない）"""
    last_err = None
    for gpu in GPU_CANDIDATES:
        body = {
            "name": name,
            "imageName": IMAGE,
            "gpuTypeIds": [gpu],
            "gpuCount": 1,
            "containerDiskInGb": 60,  # buildah レイヤー + イメージ展開で 30〜40 GB 使う
            "ports": ["22/tcp"],
            "cloudType": "SECURE",
            "dataCenterIds": [DATACENTER],
        }
        try:
            r = rest_post(api_key, "/pods", body)
            pod_id = r.get("id")
            if pod_id:
                print(f"  GPU 確保: {gpu}")
                return pod_id
        except RuntimeError as e:
            last_err = e
            print(f"  {gpu} 不可: {str(e)[:120]}")
            continue
    sys.exit(f"❌ 全 GPU 候補で Pod 作成失敗: {last_err}")


def wait_ssh(api_key, pod_id, max_wait=300):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            q = f'{{ pod(input: {{ podId: "{pod_id}" }}) {{ runtime {{ ports {{ ip privatePort publicPort type }} }} }} }}'
            r = gql(api_key, q)
            runtime = r["data"]["pod"]["runtime"]
            if runtime:
                for p in runtime["ports"]:
                    if p["privatePort"] == 22 and p["type"] == "tcp":
                        return p["ip"], p["publicPort"]
        except Exception:
            pass
        elapsed = int(time.time() - start)
        print(f"  SSH 待機中... ({elapsed}s)", flush=True)
        time.sleep(8)
    sys.exit("❌ SSH 起動タイムアウト")


def ssh_run(ip, port, cmd, stream=False, env_vars=None):
    if env_vars:
        prefix = " ".join(f"export {k}='{v}';" for k, v in env_vars.items())
        cmd = f"{prefix} {cmd}"
    args = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        f"root@{ip}", "-p", str(port), "-i", SSH_KEY, cmd,
    ]
    if stream:
        return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return subprocess.run(args, capture_output=True, text=True)


def verify_ssh(ip, port, retries=15):
    for i in range(retries):
        r = ssh_run(ip, port, "echo OK")
        if r.returncode == 0 and "OK" in r.stdout:
            return True
        time.sleep(8)
    sys.exit("❌ SSH 疎通失敗")


def terminate_pod(api_key, pod_id):
    try:
        rest_delete(api_key, f"/pods/{pod_id}")
    except Exception:
        try:
            gql(api_key, f'mutation {{ podTerminate(input: {{ podId: "{pod_id}" }}) }}')
        except Exception as e:
            print(f"  ⚠️ Pod 削除失敗: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-tag", default=DEFAULT_TAG)
    parser.add_argument("--keep-pod", action="store_true")
    args = parser.parse_args()

    api_key = get_env("RUNPOD_API_KEY")
    if not api_key:
        sys.exit("❌ RUNPOD_API_KEY 未設定")
    pat = get_env("GHCR_PAT")
    if not pat:
        sys.exit("❌ GHCR_PAT 未設定（GitHub PAT, write:packages 権限）")

    name = f"acestep-builder-{int(time.time()) & 0xFFFF}"
    print(f"🚀 Pod 作成 (dc={DATACENTER}, image={IMAGE})...")
    pod_id = create_pod(api_key, name)
    print(f"  pod_id={pod_id}")

    try:
        ip, port = wait_ssh(api_key, pod_id)
        print(f"  SSH: {ip}:{port}")
        verify_ssh(ip, port)
        print("  ✅ SSH 疎通 OK")

        # Step 1: buildah / git をインストール
        print("\n📦 Pod 環境セットアップ（buildah / skopeo / git）...")
        cmd = (
            "set -e; export DEBIAN_FRONTEND=noninteractive; "
            "apt-get update -qq && "
            "apt-get install -y -qq buildah skopeo git fuse-overlayfs uidmap 2>&1 | tail -3; "
            "buildah --version; skopeo --version"
        )
        r = ssh_run(ip, port, cmd)
        print(f"  {r.stdout.strip()}")
        if r.returncode != 0:
            print(f"  stderr: {r.stderr[:500]}")
            sys.exit("❌ buildah セットアップ失敗")

        # Step 2: リポジトリ clone
        print("\n📥 リポジトリ clone...")
        cmd = f"set -e; cd /workspace && git clone --depth=1 {REPO_URL} OssMovieAIz && cd OssMovieAIz && git log --oneline -1"
        r = ssh_run(ip, port, cmd)
        print(f"  {r.stdout.strip()}")
        if r.returncode != 0:
            print(f"  ❌ git clone 失敗: {r.stderr[:300]}")
            sys.exit(1)

        # Step 3: GHCR ログイン
        print("\n🔐 GHCR login...")
        cmd = (
            "set -e; "
            "echo \"$GHCR_PAT\" | buildah login --username keeeeeNinja --password-stdin ghcr.io 2>&1"
        )
        r = ssh_run(ip, port, cmd, env_vars={"GHCR_PAT": pat})
        print(f"  {r.stdout.strip()}")
        if r.returncode != 0:
            print(f"  ❌ GHCR ログイン失敗: {r.stderr[:300]}")
            sys.exit(1)

        # Step 4: ビルド（chroot isolation で privileged 不要）
        print(f"\n🔨 buildah bud（推定 8〜15 分）→ {args.image_tag}")
        cmd = (
            f"set -e; cd /workspace/OssMovieAIz && "
            f"buildah bud --isolation chroot --layers "
            f"-f docker/Dockerfile.acestep "
            f"-t {args.image_tag} . 2>&1"
        )
        proc = ssh_run(ip, port, cmd, stream=True)
        last_lines = []
        for line in proc.stdout:
            print(f"  {line}", end="", flush=True)
            last_lines.append(line)
            if len(last_lines) > 50:
                last_lines.pop(0)
        proc.wait()
        if proc.returncode != 0:
            print(f"\n  ❌ buildah bud 失敗 (exit {proc.returncode})")
            sys.exit(1)
        print("  ✅ ビルド完了")

        # Step 5: GHCR push
        print(f"\n📤 buildah push → GHCR...")
        cmd = f"set -e; buildah push {args.image_tag} 2>&1"
        proc = ssh_run(ip, port, cmd, stream=True)
        for line in proc.stdout:
            print(f"  {line}", end="", flush=True)
        proc.wait()
        if proc.returncode != 0:
            print(f"\n  ❌ buildah push 失敗 (exit {proc.returncode})")
            sys.exit(1)
        print("  ✅ push 完了")

        print(f"\n🎉 完了: {args.image_tag}")

    finally:
        if not args.keep_pod:
            print(f"\n🧹 Pod 終了: {pod_id}")
            terminate_pod(api_key, pod_id)
        else:
            print(f"\n⏸ Pod 保持中: {pod_id}（手動で terminate してください）")


if __name__ == "__main__":
    main()

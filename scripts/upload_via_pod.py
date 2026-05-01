#!/usr/bin/env python3
"""一時 Pod を立て、HF→Volume へ wget で直接書き込む。

Mac 経由 S3 アップロードは EU-RO-1 まで距離があり 5 MB/s 程度しか出ないため、
Volume と同じデータセンターに Pod を立てて Pod 内 wget で書き込む方が高速。
HF→Pod は 100 MB/s 以上出るので、12.7 GB の Schnell GGUF が約 2-3 分で完了する。

Usage:
  python3 scripts/upload_via_pod.py \\
    --url https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q8_0.gguf \\
    --dest /runpod-volume/ComfyUI/models/unet/flux1-schnell-Q8_0.gguf

  # 複数ファイル: カンマ区切りで url:dest を渡す
  python3 scripts/upload_via_pod.py --bulk \\
    "url1=>dest1" \\
    "url2=>dest2"
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

_env_candidates = [
    Path.cwd() / ".env",
    Path.home() / ".config" / "ossmovie" / ".env",
]
for _path in _env_candidates:
    if _path.exists():
        load_dotenv(_path, override=True)
        break

GRAPHQL = "https://api.runpod.io/graphql"
REST_BASE = "https://rest.runpod.io/v1"
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
VOLUME_ID = os.environ.get("RUNPOD_VOLUME_ID", "c1dbeweh5j")
DATACENTER = "EU-RO-1"
# wget だけなので最小 GPU で良い。RTX A4000 ≈ $0.17/hr、5 分使用で $0.014
# 在庫優先で 4090 / A4000 / 3090 をフォールバック
GPU_CANDIDATES = [
    "NVIDIA GeForce RTX 4090",
    "NVIDIA RTX A4000",
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 5090",
]
IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"


def get_api_key():
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key:
        try:
            r = subprocess.run(
                ["zsh", "-c", "source ~/.zshrc 2>/dev/null; echo $RUNPOD_API_KEY"],
                capture_output=True, text=True, timeout=5,
            )
            key = r.stdout.strip()
        except Exception:
            pass
    if not key:
        sys.exit("❌ RUNPOD_API_KEY が未設定")
    return key


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


def get_hf_token():
    """Mac の環境変数 → ~/.zshrc → 空 の優先順で HF_TOKEN を取得（任意）"""
    t = os.environ.get("HF_TOKEN", "")
    if t:
        return t
    try:
        r = subprocess.run(
            ["zsh", "-c", "source ~/.zshrc 2>/dev/null; echo $HF_TOKEN"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def create_pod(api_key, name):
    """Network Volume を /runpod-volume にマウントした GPU Pod を作成（最小 GPU 優先）"""
    # HF_TOKEN を Mac から取って Pod env に直接渡す（RunPod Secret に依存しない）。
    # gated repo (Schnell, Dev 等) の wget でこのトークンを使う。短命 Pod なので OK。
    hf_token = get_hf_token()
    env_vars = {}
    if hf_token:
        env_vars = {"HF_TOKEN": hf_token}

    last_err = None
    for gpu in GPU_CANDIDATES:
        body = {
            "name": name,
            "imageName": IMAGE,
            "gpuTypeIds": [gpu],
            "gpuCount": 1,
            "networkVolumeId": VOLUME_ID,
            "containerDiskInGb": 5,
            "ports": ["22/tcp"],
            "cloudType": "SECURE",
            "dataCenterIds": [DATACENTER],
        }
        if env_vars:
            body["env"] = env_vars
        try:
            r = rest_post(api_key, "/pods", body)
            pod_id = r.get("id")
            if pod_id:
                print(f"  GPU 確保: {gpu}  (HF_TOKEN: {'付与' if hf_token else 'なし'})")
                return pod_id
        except RuntimeError as e:
            last_err = e
            print(f"  {gpu} 不可: {str(e)[:120]}")
            continue
    sys.exit(f"❌ 全 GPU 候補で Pod 作成失敗。最終エラー: {last_err}")


def gql_get_runtime(api_key, pod_id):
    q = f'{{ pod(input: {{ podId: "{pod_id}" }}) {{ runtime {{ ports {{ ip privatePort publicPort type }} }} }} }}'
    return gql(api_key, q)


def wait_ssh(api_key, pod_id, max_wait=300):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = gql_get_runtime(api_key, pod_id)
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


def ssh_run(ip, port, cmd, stream=False, with_hf_token=False):
    """Pod に SSH してコマンドを実行。
    with_hf_token=True の場合、Mac の HF_TOKEN を export してから実行
    （RunPod の sshd は Docker container env を継承しないため、毎回明示的に渡す）。"""
    if with_hf_token:
        tok = get_hf_token()
        if tok:
            # 安全のため値は echo しない (set +x). HF_TOKEN を頭で export.
            cmd = f"export HF_TOKEN='{tok}'; {cmd}"
    args = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        f"root@{ip}", "-p", str(port), "-i", SSH_KEY, cmd,
    ]
    if stream:
        return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return subprocess.run(args, capture_output=True, text=True)


def verify_ssh(ip, port, retries=10):
    for i in range(retries):
        r = ssh_run(ip, port, "echo OK")
        if r.returncode == 0 and "OK" in r.stdout:
            return True
        time.sleep(8)
    sys.exit("❌ SSH 疎通失敗")


def probe_hf_token(ip, port):
    """Pod 内で HF_TOKEN env が見えるか確認（値は出さない）"""
    r = ssh_run(ip, port,
                "if [ -n \"${HF_TOKEN:-}\" ]; then echo \"HF_TOKEN present (len=${#HF_TOKEN})\"; "
                "else echo \"HF_TOKEN missing\"; fi")
    if r.returncode == 0:
        print(f"  Pod env: {r.stdout.strip()}")


def terminate_pod(api_key, pod_id):
    try:
        rest_delete(api_key, f"/pods/{pod_id}")
    except Exception as e:
        # フォールバック: GraphQL
        try:
            gql(api_key, f'mutation {{ podTerminate(input: {{ podId: "{pod_id}" }}) }}')
        except Exception:
            print(f"  ⚠️  Pod 削除失敗 ({pod_id}): {e}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", help="単発: ダウンロード元 URL")
    p.add_argument("--dest", help="単発: Pod 内の保存先 (例 /runpod-volume/ComfyUI/models/unet/foo.gguf)")
    p.add_argument("--bulk", nargs="+", default=[], help="複数: 'url=>dest' の組を空白区切り")
    p.add_argument("--hf-snapshot", nargs="+", default=[],
                   help="HF リポジトリ全体を Volume の HF キャッシュへ配置 "
                        "(例: --hf-snapshot Qwen/Qwen3-TTS-12Hz-1.7B-Base)。"
                        "保存先は /workspace/hf_cache（= Serverless 側で /runpod-volume/hf_cache）")
    p.add_argument("--keep-pod", action="store_true", help="完了後も Pod を残す（デバッグ用）")
    args = p.parse_args()

    def to_pod_path(p):
        # Pod では Network Volume は /workspace にマウントされる
        # （Serverless workers では /runpod-volume）
        if p.startswith("/runpod-volume/"):
            return "/workspace/" + p[len("/runpod-volume/"):]
        if not p.startswith("/workspace/"):
            print(f"  ⚠️  dest は /runpod-volume/ または /workspace/ 配下を推奨: {p}")
        return p

    jobs = []
    if args.url and args.dest:
        jobs.append((args.url, to_pod_path(args.dest)))
    for spec in args.bulk:
        if "=>" not in spec:
            sys.exit(f"❌ --bulk の書式は 'url=>dest': {spec}")
        u, d = spec.split("=>", 1)
        jobs.append((u.strip(), to_pod_path(d.strip())))
    if not jobs and not args.hf_snapshot:
        sys.exit("❌ --url/--dest, --bulk, または --hf-snapshot を指定")

    api_key = get_api_key()
    name = f"vol-uploader-{int(time.time()) & 0xFFFF}"
    print(f"🚀 Pod 作成 (dc={DATACENTER}, vol={VOLUME_ID})...")
    pod_id = create_pod(api_key, name)
    print(f"  pod_id={pod_id}")

    try:
        ip, port = wait_ssh(api_key, pod_id)
        print(f"  SSH: {ip}:{port}")
        verify_ssh(ip, port)
        print("  ✅ SSH 疎通 OK")
        probe_hf_token(ip, port)

        # HF snapshot ジョブ: hub から repo 一式を Volume の hf_cache に取得
        for repo in args.hf_snapshot:
            print(f"\n📥 HF snapshot: {repo}\n   → /workspace/hf_cache (= /runpod-volume/hf_cache)")
            cmd = (
                f"set -uo pipefail; "
                f"pip install -q -U huggingface_hub hf_transfer 2>&1 | tail -1; "
                f"export HF_HUB_ENABLE_HF_TRANSFER=1; "
                f"mkdir -p /workspace/hf_cache; "
                f"python3 -c \"from huggingface_hub import snapshot_download; "
                f"snapshot_download('{repo}', cache_dir='/workspace/hf_cache')\"; "
                f"du -sh /workspace/hf_cache"
            )
            proc = ssh_run(ip, port, cmd, stream=True)
            for line in proc.stdout:
                print(f"  {line}", end="", flush=True)
            proc.wait()
            if proc.returncode != 0:
                print(f"  ❌ HF snapshot 失敗 (exit {proc.returncode})")
            else:
                print(f"  ✅ HF snapshot 完了")

        for url, dest in jobs:
            dest_dir = os.path.dirname(dest)
            print(f"\n📥 {url}\n   → {dest}")
            # Pod 内 Python で huggingface_hub 経由 DL（HF_TOKEN は env から自動使用）。
            # 失敗時は素の wget --header フォールバック（Bearer 付き）。
            cmd = (
                f"set -uo pipefail; "
                f"mkdir -p '{dest_dir}'; cd '{dest_dir}'; "
                f"FNAME='{os.path.basename(dest)}'; URL='{url}'; "
                f"[ -L \"$FNAME\" ] && rm -f \"$FNAME\"; "
                f"echo \"[try 1] curl -L (auth=$([ -n \\\"${{HF_TOKEN:-}}\\\" ] && echo yes || echo no))\"; "
                # curl は --header の引数解釈がスペース込みでも壊れにくい
                f"if [ -n \"${{HF_TOKEN:-}}\" ]; then "
                f"  curl -fL --retry 10 --retry-delay 5 --retry-all-errors "
                f"    -H \"Authorization: Bearer $HF_TOKEN\" "
                f"    -o \"$FNAME\" \"$URL\"; "
                f"else "
                f"  curl -fL --retry 10 --retry-delay 5 --retry-all-errors "
                f"    -o \"$FNAME\" \"$URL\"; "
                f"fi; "
                f"RC=$?; "
                f"ls -lh \"$FNAME\"; "
                f"[ \"$RC\" = \"0\" ] || exit 1"
            )
            proc = ssh_run(ip, port, cmd, stream=True, with_hf_token=True)
            for line in proc.stdout:
                print(f"  {line}", end="", flush=True)
            proc.wait()
            if proc.returncode != 0:
                print(f"  ❌ 失敗 (exit {proc.returncode})")
            else:
                print(f"  ✅ 完了")
    finally:
        if not args.keep_pod:
            print(f"\n🧹 Pod 終了: {pod_id}")
            terminate_pod(api_key, pod_id)
        else:
            print(f"\n💡 Pod を残しました: {pod_id}")


if __name__ == "__main__":
    main()

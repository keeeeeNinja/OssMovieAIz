#!/usr/bin/env python3
"""
並列Pod セットアップ + 画像アップロード + Wan生成開始 一気通貫スクリプト

Usage:
  # Pod新規作成 → セットアップ → 画像アップロード
  python3 scripts/setup_parallel_pod.py \
    --scenes T2_C06,T2_C07,T2_C08,T2_C09,T2_C10 \
    --prompts scripts/wan_i2v_prompts.json

  # 既存Podにセットアップ + 画像アップロード
  python3 scripts/setup_parallel_pod.py \
    --pod-id xl19hfyvee2834 \
    --scenes T2_C06,T2_C07,T2_C08,T2_C09,T2_C10

  # セットアップ + 画像アップロード + Wan生成まで実行
  python3 scripts/setup_parallel_pod.py \
    --scenes T2_C06,T2_C07,T2_C08,T2_C09,T2_C10 \
    --prompts scripts/wan_i2v_prompts.json \
    --generate

  # Pod名を指定（デフォルト: ComfyUI-4090-N）
  python3 scripts/setup_parallel_pod.py \
    --name "ComfyUI-4090-5" \
    --scenes T1_C01,T1_C02,T1_C03

フロー:
  1. RunPod API で RTX 4090 Pod作成（--pod-id 指定時はスキップ）
  2. SSH接続を待機
  3. setup_comfyui.sh をアップロード＆実行（ComfyUI + Wan 2.1モデル一式）
  4. 指定シーンの参照画像をアップロード
  5. --generate 指定時は generate_wan_i2v.py を起動

※ containerDisk = 50GB（Wan 2.1モデル + pip packages で 20GB超必要。余裕を持って50GB）
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPT_DIR, "..")
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup_comfyui.sh")
DEFAULT_IMAGE_DIR = os.path.join(PROJECT_DIR, "作業中動画")
IMAGE_DIR = DEFAULT_IMAGE_DIR  # --image-dir で上書き可能
RUNPOD_API_URL = "https://api.runpod.io/graphql"

# --- RunPod API Key 取得 ---
def get_api_key():
    key = os.environ.get("RUNPOD_API_KEY", "")
    if not key:
        # zshrcから読み込み
        try:
            result = subprocess.run(
                ["zsh", "-c", "source ~/.zshrc 2>/dev/null; echo $RUNPOD_API_KEY"],
                capture_output=True, text=True, timeout=5
            )
            key = result.stdout.strip()
        except Exception:
            pass
    if not key:
        print("❌ RUNPOD_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)
    return key


def runpod_query(api_key, query):
    """RunPod GraphQL APIにクエリを送信"""
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        RUNPOD_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def ssh_cmd(ip, port, cmd, timeout=30, check=True):
    """SSH経由でコマンドを実行"""
    full_cmd = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", f"ConnectTimeout={timeout}",
        f"root@{ip}", "-p", str(port), "-i", SSH_KEY,
        cmd
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout + 10)
    if check and result.returncode != 0:
        return None
    return result.stdout.strip()


def scp_upload(ip, port, local_path, remote_path):
    """SCPでファイルをアップロード"""
    cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", str(port), "-i", SSH_KEY,
        local_path, f"root@{ip}:{remote_path}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


# =============================================================
#  Step 1: Pod作成
# =============================================================
def create_pod(api_key, name, gpu_type, region, disk_gb):
    """RunPod APIでPodを作成し、Pod IDを返す"""
    datacenter = f', dataCenterId: "{region}"' if region else ""
    mutation = f'''mutation {{
        podFindAndDeployOnDemand(input: {{
            name: "{name}",
            gpuTypeId: "{gpu_type}",
            gpuCount: 1,
            volumeInGb: 0,
            containerDiskInGb: {disk_gb},
            imageName: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
            startSsh: true,
            ports: "22/tcp,8188/http"
            {datacenter}
        }}) {{ id name desiredStatus }}
    }}'''

    result = runpod_query(api_key, mutation)
    try:
        pod = result["data"]["podFindAndDeployOnDemand"]
        return pod["id"]
    except (KeyError, TypeError):
        print(f"❌ Pod作成に失敗しました: {json.dumps(result, indent=2)}", file=sys.stderr)
        sys.exit(1)


# =============================================================
#  Step 2: SSH接続情報を待つ
# =============================================================
def wait_for_ssh(api_key, pod_id, max_wait=300):
    """Podが起動してSSH接続情報が取れるまで待つ"""
    query = f'{{ pod(input: {{ podId: "{pod_id}" }}) {{ id desiredStatus runtime {{ uptimeInSeconds ports {{ ip isIpPublic privatePort publicPort type }} }} }} }}'

    start = time.time()
    while time.time() - start < max_wait:
        try:
            result = runpod_query(api_key, query)
            runtime = result["data"]["pod"]["runtime"]
            if runtime:
                ports = runtime["ports"]
                for p in ports:
                    if p["privatePort"] == 22 and p["type"] == "tcp":
                        return p["ip"], p["publicPort"]
        except Exception:
            pass
        elapsed = int(time.time() - start)
        print(f"  待機中... ({elapsed}秒)", flush=True)
        time.sleep(10)

    print("❌ SSH接続情報の取得に失敗（タイムアウト）", file=sys.stderr)
    sys.exit(1)


# =============================================================
#  Step 3: SSH疎通確認
# =============================================================
def verify_ssh(ip, port, max_retries=6):
    """SSH接続が実際に通るか確認"""
    for i in range(1, max_retries + 1):
        out = ssh_cmd(ip, port, "echo SSH_OK", check=False)
        if out and "SSH_OK" in out:
            return True
        print(f"  リトライ中... ({i}/{max_retries})", flush=True)
        time.sleep(10)
    print("❌ SSH接続に失敗しました", file=sys.stderr)
    sys.exit(1)


# =============================================================
#  Step 4: ComfyUI + Wan 2.1 セットアップ
# =============================================================
def run_setup(ip, port):
    """setup_comfyui.sh をアップロードして実行"""
    # setup_comfyui.sh をアップロード
    if not scp_upload(ip, port, SETUP_SCRIPT, "/root/setup_comfyui.sh"):
        print("❌ setup_comfyui.sh のアップロードに失敗", file=sys.stderr)
        sys.exit(1)

    # 実行（ストリーミング出力）
    cmd = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        f"root@{ip}", "-p", str(port), "-i", SSH_KEY,
        "bash /root/setup_comfyui.sh"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(f"  {line}", end="", flush=True)
    process.wait()

    if process.returncode != 0:
        print(f"⚠️  セットアップがエラーで終了（exit code: {process.returncode}）", file=sys.stderr)
        return False
    return True


# =============================================================
#  Step 5: ComfyUI起動確認
# =============================================================
def verify_comfyui(ip, port):
    """ComfyUIが起動しているか確認"""
    out = ssh_cmd(ip, port,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/",
        check=False, timeout=15)
    return out and out.strip() == "200"


# =============================================================
#  Step 6: 画像アップロード
# =============================================================
def upload_images(ip, port, scene_ids, prompts):
    """指定シーンの参照画像をPodにアップロード"""
    # プロンプトJSONから画像名を取得
    image_map = {p["id"]: p["image"] for p in prompts}
    images_to_upload = []
    for sid in scene_ids:
        if sid in image_map:
            images_to_upload.append(image_map[sid])
        else:
            print(f"  ⚠️  シーン {sid} がプロンプトJSONに見つかりません", file=sys.stderr)

    if not images_to_upload:
        print("  アップロードする画像がありません")
        return

    # リモートの既存画像を確認
    existing = ssh_cmd(ip, port, "ls /workspace/ComfyUI/input/ 2>/dev/null", check=False) or ""
    existing_files = set(existing.split())

    uploaded = 0
    for img in images_to_upload:
        if img in existing_files:
            continue
        local_path = os.path.join(IMAGE_DIR, img)
        if not os.path.exists(local_path):
            print(f"  ⚠️  ローカルに画像がありません: {local_path}", file=sys.stderr)
            continue
        if scp_upload(ip, port, local_path, f"/workspace/ComfyUI/input/{img}"):
            uploaded += 1
        else:
            print(f"  ⚠️  アップロード失敗: {img}", file=sys.stderr)

    print(f"  {uploaded}/{len(images_to_upload)} 枚アップロード完了")


# =============================================================
#  Main
# =============================================================
def main():
    parser = argparse.ArgumentParser(description="並列Pod一気通貫セットアップ")
    parser.add_argument("--pod-id", default="", help="既存Pod ID（指定時はPod作成をスキップ）")
    parser.add_argument("--name", default="", help="Pod名（デフォルト: ComfyUI-4090-N）")
    parser.add_argument("--gpu", default="NVIDIA GeForce RTX 4090", help="GPUタイプ")
    parser.add_argument("--region", default="", help="リージョン（空=Any）")
    parser.add_argument("--disk", default=50, type=int, help="containerDisk GB（デフォルト: 50）")
    parser.add_argument("--scenes", required=True, help="シーンIDをカンマ区切り（例: T2_C06,T2_C07,...）")
    parser.add_argument("--prompts", default=os.path.join(SCRIPT_DIR, "wan_i2v_prompts.json"),
                        help="プロンプトJSONファイル")
    parser.add_argument("--generate", action="store_true",
                        help="セットアップ後にWan生成も実行する")
    parser.add_argument("--image-dir", default="", help="画像ディレクトリ（デフォルト: 作業中動画/）")
    args = parser.parse_args()

    # 画像ディレクトリの上書き
    global IMAGE_DIR
    if args.image_dir:
        IMAGE_DIR = args.image_dir

    scene_ids = [s.strip() for s in args.scenes.split(",")]
    api_key = get_api_key()

    # プロンプトJSON読み込み
    with open(args.prompts) as f:
        prompts = json.load(f)

    # --- Step 1: Pod作成 or 既存Pod ---
    if args.pod_id:
        pod_id = args.pod_id
        print(f"既存Pod使用: {pod_id}")
    else:
        name = args.name or f"ComfyUI-4090-{len(scene_ids)}"
        print("=" * 50)
        print(f"  並列Pod作成（Volume なし）")
        print(f"  GPU: {args.gpu}")
        print(f"  Disk: {args.disk}GB")
        print(f"  シーン: {', '.join(scene_ids)}")
        print("=" * 50)
        print()
        print("[1/6] Pod作成中...")
        pod_id = create_pod(api_key, name, args.gpu, args.region, args.disk)
        print(f"  Pod ID: {pod_id}")

    # --- Step 2: SSH接続情報を待つ ---
    print()
    print("[2/6] SSH接続情報を待機中...")
    ip, port = wait_for_ssh(api_key, pod_id)
    print(f"  SSH: root@{ip} -p {port}")

    # --- Step 3: SSH疎通確認 ---
    print()
    print("[3/6] SSH接続を確認中...")
    verify_ssh(ip, port)
    print("  SSH接続OK")

    # --- Step 4: セットアップ ---
    print()
    print("[4/6] ComfyUI + Wan 2.1 セットアップ中（約5-10分）...")
    run_setup(ip, port)

    # --- Step 5: ComfyUI起動確認 ---
    print()
    print("[5/6] ComfyUI起動を確認中...")
    # セットアップ直後は起動中の可能性があるのでリトライ
    for i in range(6):
        if verify_comfyui(ip, port):
            print("  ComfyUI: OK (port 8188)")
            break
        if i < 5:
            print(f"  待機中... ({(i+1)*10}秒)")
            time.sleep(10)
    else:
        print("  ⚠️  ComfyUIの起動確認に失敗。手動で確認してください")

    # --- Step 6: 画像アップロード ---
    print()
    print("[6/6] 参照画像をアップロード中...")
    upload_images(ip, port, scene_ids, prompts)

    # --- 完了 ---
    print()
    print("=" * 50)
    print("  ✅ 並列Podセットアップ完了")
    print("=" * 50)
    print(f"  Pod ID:  {pod_id}")
    print(f"  SSH:     ssh root@{ip} -p {port} -i ~/.ssh/id_ed25519")
    print(f"  シーン:  {', '.join(scene_ids)}")
    print()

    # --- オプション: Wan生成実行 ---
    if args.generate:
        print("Wan 2.1 I2V 生成を開始します...")
        print()
        gen_cmd = [
            sys.executable, os.path.join(SCRIPT_DIR, "generate_wan_i2v.py"),
            "--host", ip, "--port", str(port),
            "--prompts", args.prompts,
            "--scenes", ",".join(scene_ids),
            "--pod-id", pod_id, "--terminate"
        ]
        os.execvp(sys.executable, gen_cmd)
    else:
        print("  Wan生成コマンド:")
        print(f"  python3 scripts/generate_wan_i2v.py \\")
        print(f"    --host {ip} --port {port} \\")
        print(f"    --prompts {args.prompts} \\")
        print(f"    --scenes {','.join(scene_ids)} \\")
        print(f"    --pod-id {pod_id} --terminate")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
並列Pod セットアップ + Wan I2V 生成 一気通貫スクリプト（Wan専用機）

このスクリプトで作成するPodはWan 2.1 I2V専用です。
Flux静止画の生成はPod1（Network Volume付き）で行い、
生成済み画像をローカル経由でこのPodにアップロードしてWan生成を行います。

Usage:
  # 【推奨】Wan専用Pod作成 → 画像アップロード → Wan生成
  python3 scripts/setup_parallel_pod.py \
    --wan-prompts scripts/wan_i2v_prompts.json \
    --image-dir 作業中動画/theme2 \
    --generate

  # 既存PodでWan生成
  python3 scripts/setup_parallel_pod.py \
    --pod-id xl19hfyvee2834 \
    --scenes T2_C06,T2_C07,T2_C08 \
    --wan-prompts scripts/wan_i2v_prompts.json \
    --image-dir 作業中動画/theme2 \
    --generate

フロー:
  1. RunPod API で RTX 4090 Pod作成（--pod-id 指定時はスキップ）
  2. SSH接続を待機
  3. setup_comfyui.sh --wan-only をアップロード＆実行（Wan 2.1のみ、Flux/LoRAはスキップ）
  4. Pod1で生成済みのFlux画像をローカルからアップロード
  5. --generate 指定時は generate_wan_i2v.py を起動（Wan I2V）

※ containerDisk = 50GB（Wan 2.1 GGUF 12GB + text encoders 5GB + pip/ComfyUI 7GB ≈ 25GB使用）
※ Flux fp8/LoRAは不要なので80GBは不要

※ `--prompts` は後方互換のため `--wan-prompts` の別名として残している
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
            "User-Agent": "RunPod-Client/1.0",
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
# 4090 が在庫切れの場合のフォールバック順序
# （メモリ: 3090 は使わない。5090 にフォールバックしてスピード優先）
GPU_PRIMARY = "NVIDIA GeForce RTX 4090"
GPU_FALLBACK = "NVIDIA GeForce RTX 5090"
PRIMARY_WAIT_SECONDS = 300  # 4090 を 5分待つ
PRIMARY_RETRY_INTERVAL = 30  # 30秒間隔でリトライ

# GPU別Dockerイメージ
DOCKER_IMAGES = {
    GPU_PRIMARY: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
    GPU_FALLBACK: "runpod/pytorch:2.8.0-py3.12-cuda12.8.1-devel-ubuntu22.04",
}


def _try_create_pod(api_key, name, gpu_type, region, disk_gb):
    """単発でPod作成を試す。成功時はpod_id、失敗時はNoneを返す"""
    datacenter = f', dataCenterId: "{region}"' if region else ""
    # HF_TOKEN は RunPod Secret から参照（将来のモデルDL用に設定）
    env_block = 'env: [{ key: "HF_TOKEN", value: "{{ RUNPOD_SECRET_HF_TOKEN }}" }],'
    mutation = f'''mutation {{
        podFindAndDeployOnDemand(input: {{
            name: "{name}",
            gpuTypeId: "{gpu_type}",
            gpuCount: 1,
            volumeInGb: 0,
            containerDiskInGb: {disk_gb},
            imageName: "{DOCKER_IMAGES.get(gpu_type, DOCKER_IMAGES[GPU_PRIMARY])}",
            startSsh: true,
            ports: "22/tcp,8188/http",
            {env_block}
            {datacenter}
        }}) {{ id name desiredStatus }}
    }}'''

    try:
        result = runpod_query(api_key, mutation)
    except Exception as e:
        print(f"  API呼び出しエラー: {e}", file=sys.stderr)
        return None

    try:
        pod = result["data"]["podFindAndDeployOnDemand"]
        if pod and pod.get("id"):
            return pod["id"]
    except (KeyError, TypeError):
        pass
    return None


def create_pod(api_key, name, gpu_type, region, disk_gb):
    """
    Pod作成。gpu_type が GPU_PRIMARY なら在庫切れ時に以下の挙動:
      1. 4090 を 5分間リトライ（30秒間隔）
      2. ダメなら 5090 に即フォールバック
      3. それもダメなら終了
    gpu_type が明示的に指定されていれば（4090 以外）、単発試行のみ。
    """
    # 明示的に 4090 以外を指定された場合はフォールバックしない
    if gpu_type != GPU_PRIMARY:
        pod_id = _try_create_pod(api_key, name, gpu_type, region, disk_gb)
        if pod_id:
            return pod_id, gpu_type
        print(f"❌ Pod作成に失敗しました（GPU: {gpu_type}）", file=sys.stderr)
        sys.exit(1)

    # 4090 を最大 5分リトライ
    print(f"  4090 を最大 {PRIMARY_WAIT_SECONDS}秒リトライ...")
    start = time.time()
    attempt = 0
    while time.time() - start < PRIMARY_WAIT_SECONDS:
        attempt += 1
        pod_id = _try_create_pod(api_key, name, GPU_PRIMARY, region, disk_gb)
        if pod_id:
            print(f"  4090 確保成功（{attempt}回目, {int(time.time() - start)}秒経過）")
            return pod_id, GPU_PRIMARY
        elapsed = int(time.time() - start)
        remaining = PRIMARY_WAIT_SECONDS - elapsed
        if remaining <= 0:
            break
        wait = min(PRIMARY_RETRY_INTERVAL, remaining)
        print(f"  4090 在庫なし（{attempt}回目, {elapsed}秒経過） — {wait}秒後に再試行")
        time.sleep(wait)

    # 5090 にフォールバック
    print(f"  4090 を {PRIMARY_WAIT_SECONDS}秒待ちましたが在庫切れ → 5090 にフォールバック")
    fallback_name = name.replace("4090", "5090") if "4090" in name else name
    pod_id = _try_create_pod(api_key, fallback_name, GPU_FALLBACK, region, disk_gb)
    if pod_id:
        print(f"  5090 確保成功")
        return pod_id, GPU_FALLBACK

    print(f"❌ 4090・5090 ともに在庫切れで Pod 作成に失敗しました", file=sys.stderr)
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
def run_setup(ip, port, gpu_type=GPU_PRIMARY):
    """setup_comfyui.sh をアップロードして実行"""
    # setup_comfyui.sh をアップロード
    if not scp_upload(ip, port, SETUP_SCRIPT, "/root/setup_comfyui.sh"):
        print("❌ setup_comfyui.sh のアップロードに失敗", file=sys.stderr)
        sys.exit(1)

    # 5090の場合は --5090 フラグを追加
    setup_flags = "--wan-only --5090" if gpu_type == GPU_FALLBACK else "--wan-only"

    # 実行（ストリーミング出力）
    cmd = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        f"root@{ip}", "-p", str(port), "-i", SSH_KEY,
        f"bash /root/setup_comfyui.sh {setup_flags}"
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

    # リモートの既存画像を確認（キャッシュは必ず削除して最新に置換する）
    existing = ssh_cmd(ip, port, "ls /workspace/ComfyUI/input/ 2>/dev/null", check=False) or ""
    existing_files = set(existing.split())

    uploaded = 0
    replaced = 0
    for img in images_to_upload:
        local_path = os.path.join(IMAGE_DIR, img)
        if not os.path.exists(local_path):
            print(f"  ⚠️  ローカルに画像がありません: {local_path}", file=sys.stderr)
            continue
        if img in existing_files:
            ssh_cmd(ip, port, f"rm -f /workspace/ComfyUI/input/{img}", check=False)
            replaced += 1
        if scp_upload(ip, port, local_path, f"/workspace/ComfyUI/input/{img}"):
            uploaded += 1
        else:
            print(f"  ⚠️  アップロード失敗: {img}", file=sys.stderr)

    print(f"  {uploaded}/{len(images_to_upload)} 枚アップロード完了" + (f"（うちキャッシュ置換 {replaced} 件）" if replaced else ""))


# =============================================================
#  Main
# =============================================================
def main():
    parser = argparse.ArgumentParser(description="並列Pod一気通貫セットアップ")
    parser.add_argument("--pod-id", default="", help="既存Pod ID（指定時はPod作成をスキップ）")
    parser.add_argument("--name", default="", help="Pod名（デフォルト: ComfyUI-4090-N）")
    parser.add_argument("--gpu", default="NVIDIA GeForce RTX 4090", help="GPUタイプ")
    parser.add_argument("--region", default="", help="リージョン（空=Any）")
    parser.add_argument("--disk", default=50, type=int, help="containerDisk GB（デフォルト: 50、Wan専用なので80は不要）")
    parser.add_argument("--scenes", default="",
                        help="シーンIDをカンマ区切り。省略時は プロンプトJSONの全IDを対象にしてロックで分配（推奨）")
    # --prompts は後方互換。新規は --wan-prompts を使う
    parser.add_argument("--prompts", default="", help="[deprecated] --wan-prompts の旧名")
    parser.add_argument("--wan-prompts", default="", help="Wan I2V プロンプトJSON")
    parser.add_argument("--flux-prompts", default="",
                        help="[廃止] Flux生成はPod1専用。指定するとエラーになります")
    parser.add_argument("--generate", action="store_true",
                        help="セットアップ後にWan生成も実行する")
    parser.add_argument("--image-dir", default="", help="[旧互換] ローカルに既存の参照画像を置くディレクトリ")
    parser.add_argument("--output-dir", default="",
                        help="Wan出力の保存先ディレクトリ（単一テーマ用）")
    parser.add_argument("--output-root", default="",
                        help="並列プールモードのルートディレクトリ（例: 作業中動画）。指定するとシーンIDのT{N}_から theme{N}/ へ自動ルーティング。--output-dir と排他")
    args = parser.parse_args()

    if args.flux_prompts:
        print("❌ --flux-prompts は廃止されました。Flux画像生成はPod1（Network Volume付き）専用です。", file=sys.stderr)
        print("   Pod1で generate_flux_images.py を使って生成してください。", file=sys.stderr)
        sys.exit(1)

    if args.output_root and args.output_dir:
        print("❌ --output-root と --output-dir は同時指定できません", file=sys.stderr)
        sys.exit(1)

    # --prompts / --wan-prompts を正規化
    wan_prompts_path = args.wan_prompts or args.prompts or os.path.join(SCRIPT_DIR, "wan_i2v_prompts.json")

    # 画像ディレクトリ / 出力先の上書き
    global IMAGE_DIR
    pooled_mode = bool(args.output_root)
    if pooled_mode:
        output_dir = args.output_root
        IMAGE_DIR = args.output_root
    else:
        output_dir = args.output_dir or args.image_dir or DEFAULT_IMAGE_DIR
        if args.image_dir:
            IMAGE_DIR = args.image_dir
        elif args.output_dir:
            IMAGE_DIR = args.output_dir

    api_key = get_api_key()

    # Wan プロンプトJSON読み込み
    with open(wan_prompts_path) as f:
        prompts = json.load(f)

    # --scenes 省略時は全シーンを対象にしてロックで分配
    if args.scenes:
        scene_ids = [s.strip() for s in args.scenes.split(",")]
    else:
        scene_ids = [p["id"] for p in prompts]
        print(f"  --scenes 未指定 → プロンプトJSONの全 {len(scene_ids)} シーンを対象にプール運用")

    # --- Step 1: Pod作成 or 既存Pod ---
    actual_gpu = GPU_PRIMARY  # デフォルト（既存Pod使用時）
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
        pod_id, actual_gpu = create_pod(api_key, name, args.gpu, args.region, args.disk)
        print(f"  Pod ID: {pod_id}")
        print(f"  GPU:    {actual_gpu}")

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
    run_setup(ip, port, actual_gpu)

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

    # --- Step 6: Pod1で生成済みのFlux画像をアップロード ---
    print()
    print("[6/6] 参照画像をアップロード中（Pod1で生成済みのFlux画像）...")
    upload_images(ip, port, scene_ids, prompts)

    # --- 完了 ---
    print()
    print("=" * 50)
    print("  ✅ 並列Podセットアップ完了")
    print("=" * 50)
    print(f"  Pod ID:  {pod_id}")
    print(f"  SSH:     ssh root@{ip} -p {port} -i ~/.ssh/id_ed25519")
    print(f"  シーン:  {', '.join(scene_ids)}")
    print(f"  モード:  Wan専用（Flux/LoRAなし）")
    print()

    # --- オプション: Wan生成実行 ---
    if args.generate:
        print("Wan 2.1 I2V 生成を開始します...")
        print()
        gen_cmd = [
            sys.executable, os.path.join(SCRIPT_DIR, "generate_wan_i2v.py"),
            "--host", ip, "--port", str(port),
            "--prompts", wan_prompts_path,
            "--scenes", ",".join(scene_ids),
            "--pod-id", pod_id, "--terminate"
        ]
        if pooled_mode:
            gen_cmd += ["--output-root", args.output_root]
        else:
            gen_cmd += ["--output-dir", output_dir]
        os.execvp(sys.executable, gen_cmd)
    else:
        dir_flag = f"--output-root {args.output_root}" if pooled_mode else f"--output-dir {output_dir}"
        print("  Wan生成コマンド:")
        print(f"  python3 scripts/generate_wan_i2v.py \\")
        print(f"    --host {ip} --port {port} \\")
        print(f"    --prompts {wan_prompts_path} \\")
        print(f"    --scenes {','.join(scene_ids)} \\")
        print(f"    {dir_flag} \\")
        print(f"    --pod-id {pod_id} --terminate")


if __name__ == "__main__":
    main()

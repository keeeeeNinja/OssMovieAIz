#!/usr/bin/env python3
"""
Flux Kontext LoRA Dataset Generator via ComfyUI on RunPod

Usage:
  python3 scripts/generate_kontext_dataset.py \
    --host IP --port PORT \
    --seed-image 作業中動画/lora_source/xxx.png \
    --prompts 作業中動画/lora_source/rin_chan_prompts.json \
    --output-dir 作業中動画/lora_source/dataset

  # 特定のプロンプトだけ再生成
  python3 scripts/generate_kontext_dataset.py ... --scenes R01,R02

種画像を ComfyUI の input/ にアップロードし、各プロンプトで Kontext ワークフローを実行して、
生成画像を output-dir にダウンロードする。LoRA 学習データセット作成用。
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
COMFYUI_OUTPUT_DIR = "/workspace/ComfyUI/output"
COMFYUI_INPUT_DIR = "/workspace/ComfyUI/input"


def ssh(host, port, cmd, check=True, timeout=60):
    full_cmd = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        f"root@{host}", "-p", str(port), "-i", SSH_KEY,
        cmd,
    ]
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if check:
            print(f"SSH timeout after {timeout}s", file=sys.stderr)
            sys.exit(1)
        return ""
    if check and result.returncode != 0:
        print(f"SSH error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def scp_upload(host, port, local_path, remote_path, timeout=300):
    cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-P", str(port), "-i", SSH_KEY,
        local_path, f"root@{host}:{remote_path}",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def scp_download(host, port, remote_path, local_path, timeout=300):
    cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15",
        "-P", str(port), "-i", SSH_KEY,
        f"root@{host}:{remote_path}", local_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def check_comfyui(host, port):
    out = ssh(host, port,
              "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/",
              check=False)
    return out.strip() == "200"


def build_kontext_workflow(prompt_text, prefix, seed_image_name, seed,
                           steps=20, guidance=2.5):
    """Flux Kontext (GGUF Q8) LoRAデータセット生成ワークフロー"""
    wf = {
        "30": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "flux1-kontext-dev-Q8_0.gguf"},
        },
        "31": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux",
            },
        },
        "32": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "33": {
            "class_type": "LoadImage",
            "inputs": {"image": seed_image_name},
        },
        "34": {
            "class_type": "FluxKontextImageScale",
            "inputs": {"image": ["33", 0]},
        },
        "35": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["34", 0], "vae": ["32", 0]},
        },
        "36": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["31", 0]},
        },
        "37": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["31", 0]},
        },
        "38": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["36", 0], "guidance": guidance},
        },
        "39": {
            "class_type": "ReferenceLatent",
            "inputs": {"conditioning": ["38", 0], "latent": ["35", 0]},
        },
        "40": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["30", 0],
                "positive": ["39", 0],
                "negative": ["37", 0],
                "latent_image": ["35", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "41": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["40", 0], "vae": ["32", 0]},
        },
        "42": {
            "class_type": "SaveImage",
            "inputs": {"images": ["41", 0], "filename_prefix": prefix},
        },
    }
    return wf


def submit_workflow(host, port, workflow):
    import tempfile
    payload = json.dumps({"prompt": workflow})
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload)
        tmp_local = f.name
    tmp_remote = "/tmp/kontext_payload.json"
    subprocess.run([
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", str(port), "-i", SSH_KEY,
        tmp_local, f"root@{host}:{tmp_remote}",
    ], capture_output=True)
    os.unlink(tmp_local)

    cmd = f"curl -s -X POST http://localhost:8188/prompt -H 'Content-Type: application/json' -d @{tmp_remote}"
    out = ssh(host, port, cmd, check=False)
    try:
        resp = json.loads(out)
        if "error" in resp:
            print(f"  API error: {resp['error']}", file=sys.stderr)
            if "node_errors" in resp:
                print(f"  node_errors: {json.dumps(resp['node_errors'], ensure_ascii=False)[:400]}",
                      file=sys.stderr)
            return ""
        return resp.get("prompt_id", "")
    except Exception:
        print(f"  Submit error: {out[:300]}", file=sys.stderr)
        return ""


def poll_until_done(host, port, prompt_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        out = ssh(host, port,
                  f"curl -s --max-time 20 http://localhost:8188/history/{prompt_id}",
                  check=False, timeout=30)
        try:
            hist = json.loads(out)
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                if outputs:
                    return outputs
                status = hist[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    print(f"  [エラー] ComfyUI実行エラー: {status}", file=sys.stderr)
                    return None
        except Exception:
            pass
        elapsed = int(time.time() - start)
        print(f"  生成中... ({elapsed}s)", flush=True)
        time.sleep(10)
    return None


def find_output_file(host, port, prefix):
    out = ssh(host, port,
              f"ls -t {COMFYUI_OUTPUT_DIR}/{prefix}*.png 2>/dev/null | head -1",
              check=False)
    return out.strip()


def main():
    parser = argparse.ArgumentParser(description="Flux Kontext LoRA Dataset Generator")
    parser.add_argument("--host", required=True, help="RunPod IP")
    parser.add_argument("--port", required=True, type=int, help="RunPod SSH port")
    parser.add_argument("--seed-image", required=True, help="ローカルの種画像パス")
    parser.add_argument("--prompts", required=True, help="プロンプトJSONファイル")
    parser.add_argument("--output-dir", required=True, help="出力先ディレクトリ")
    parser.add_argument("--steps", default=20, type=int)
    parser.add_argument("--guidance", default=2.5, type=float,
                        help="FluxGuidance値（Kontextの推奨は2.5）")
    parser.add_argument("--seed", default=0, type=int,
                        help="0 なら各プロンプトでランダムseed")
    parser.add_argument("--scenes", default="",
                        help="特定のプロンプトIDだけ生成（カンマ区切り）")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"RunPodに接続中: {args.host}:{args.port}")
    if not check_comfyui(args.host, args.port):
        print("ComfyUIが起動していません", file=sys.stderr)
        sys.exit(1)
    print("ComfyUI: OK")

    # 種画像を input/ にアップロード
    seed_name = os.path.basename(args.seed_image)
    remote_seed = f"{COMFYUI_INPUT_DIR}/{seed_name}"
    print(f"\n種画像をアップロード中: {seed_name}")
    ssh(args.host, args.port, f"mkdir -p {COMFYUI_INPUT_DIR}")
    if not scp_upload(args.host, args.port, args.seed_image, remote_seed):
        print("種画像のアップロード失敗", file=sys.stderr)
        sys.exit(1)
    print("  アップロード完了")

    with open(args.prompts) as f:
        data = json.load(f)

    if isinstance(data, dict):
        prompts_list = data["prompts"]
        character = data.get("character", "character")
    else:
        prompts_list = data
        character = "character"

    if args.scenes:
        scene_filter = set(s.strip() for s in args.scenes.split(","))
        prompts_list = [p for p in prompts_list if p.get("id") in scene_filter]
        if not prompts_list:
            print("⚠️  フィルタに合致するプロンプトがありません", file=sys.stderr)
            sys.exit(1)

    print(f"\nキャラ: {character}")
    print(f"対象: {len(prompts_list)} プロンプト")
    print(f"出力: {args.output_dir}")
    print(f"Steps: {args.steps}, Guidance: {args.guidance}")

    results = []
    for i, item in enumerate(prompts_list, 1):
        cut_id = item["id"]
        prompt_text = item["text"]
        prefix = f"{character.lower()}_{cut_id}"
        local_file = os.path.join(args.output_dir, f"{prefix}.png")

        if os.path.exists(local_file):
            print(f"\n[{cut_id}] スキップ（既存ファイル）")
            results.append({"id": cut_id, "status": "skipped", "file": local_file})
            continue

        print(f"\n[{cut_id}] 生成開始 ({i}/{len(prompts_list)})")
        print(f"  cat: {item.get('cat', '-')}  framing: {item.get('framing', '-')}")
        print(f"  prompt: {prompt_text[:90]}...")

        seed = args.seed if args.seed > 0 else random.randint(1, 2**32)
        wf = build_kontext_workflow(
            prompt_text, prefix, seed_name, seed,
            steps=args.steps, guidance=args.guidance,
        )

        prompt_id = submit_workflow(args.host, args.port, wf)
        if not prompt_id:
            results.append({"id": cut_id, "status": "error"})
            continue

        print(f"  prompt_id: {prompt_id}")
        outputs = poll_until_done(args.host, args.port, prompt_id)
        if not outputs:
            results.append({"id": cut_id, "status": "timeout"})
            continue

        remote_file = find_output_file(args.host, args.port, prefix)
        if not remote_file:
            print(f"  [エラー] 出力ファイルが見つかりません", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})
            continue

        if scp_download(args.host, args.port, remote_file, local_file):
            print(f"  ダウンロード完了: {local_file}")
            results.append({"id": cut_id, "file": local_file, "status": "ok"})
        else:
            print(f"  [エラー] ダウンロード失敗", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})

    # サマリー
    print("\n" + "=" * 50)
    print(f"Kontext データセット生成完了 ({character})")
    print("=" * 50)
    ok = sum(1 for r in results if r["status"] == "ok")
    skip = sum(1 for r in results if r["status"] == "skipped")
    err = sum(1 for r in results if r["status"] in ("error", "timeout"))
    print(f"成功: {ok}  スキップ: {skip}  エラー: {err}")
    for r in results:
        icon = {"ok": "OK", "skipped": "SKIP", "error": "ERR", "timeout": "TIMEOUT"}.get(r["status"], "?")
        print(f"  [{icon}] {r['id']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Flux Image Generator via ComfyUI on RunPod (LoRA対応)

Usage:
  python3 scripts/generate_flux_images.py \
    --host IP --port PORT \
    --prompts scripts/flux_prompts.json \
    [--lora flux_japanese_girl_v2.safetensors] \
    [--lora-strength 0.8] \
    [--steps 20] \
    [--width 768] [--height 1024]
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
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../作業中動画")
LOCAL_OUTPUT_DIR = DEFAULT_OUTPUT_DIR  # --output-dir で上書き可能


def ssh(host, port, cmd, check=True):
    full_cmd = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"root@{host}", "-p", str(port), "-i", SSH_KEY,
        cmd
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"SSH error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def scp_download(host, port, remote_path, local_path):
    cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", str(port), "-i", SSH_KEY,
        f"root@{host}:{remote_path}", local_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def check_comfyui(host, port):
    out = ssh(host, port,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/",
        check=False)
    return out.strip() == "200"


def build_workflow(prompt_text, prefix, width, height, steps, seed,
                   lora_name=None, lora_strength=0.8):
    """LoRA対応のFluxワークフローを構築"""
    wf = {
        "3": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux1-dev.safetensors",
                "weight_dtype": "fp8_e4m3fn"
            }
        },
        "4": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp16.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux"
            }
        },
        "5": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"}
        },
        "10": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1}
        },
        "12": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["11", 0], "vae": ["5", 0]}
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {"images": ["12", 0], "filename_prefix": prefix}
        }
    }

    if lora_name:
        # LoRA経由: model → LoraLoader → KSampler
        wf["20"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["3", 0],
                "clip": ["4", 0],
                "lora_name": lora_name,
                "strength_model": lora_strength,
                "strength_clip": lora_strength
            }
        }
        wf["6"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["20", 1]}
        }
        wf["11"] = {
            "class_type": "KSampler",
            "inputs": {
                "model": ["20", 0],
                "positive": ["6", 0],
                "negative": ["6", 0],
                "latent_image": ["10", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            }
        }
    else:
        # LoRAなし: model → KSampler
        wf["6"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["4", 0]}
        }
        wf["11"] = {
            "class_type": "KSampler",
            "inputs": {
                "model": ["3", 0],
                "positive": ["6", 0],
                "negative": ["6", 0],
                "latent_image": ["10", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0
            }
        }

    return wf


def submit_workflow(host, port, workflow):
    """ComfyUI APIにワークフローを投入してprompt_idを返す"""
    import tempfile
    payload = json.dumps({"prompt": workflow})
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload)
        tmp_local = f.name
    tmp_remote = "/tmp/comfy_payload.json"
    subprocess.run([
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", str(port), "-i", SSH_KEY,
        tmp_local, f"root@{host}:{tmp_remote}"
    ], capture_output=True)
    os.unlink(tmp_local)

    cmd = f"curl -s -X POST http://localhost:8188/prompt -H 'Content-Type: application/json' -d @{tmp_remote}"
    out = ssh(host, port, cmd, check=False)
    try:
        resp = json.loads(out)
        if "error" in resp:
            print(f"  API error: {resp['error']}", file=sys.stderr)
            return ""
        return resp.get("prompt_id", "")
    except Exception:
        print(f"  Submit error: {out}", file=sys.stderr)
        return ""


def poll_until_done(host, port, prompt_id, timeout=300):
    """生成完了を待つ"""
    start = time.time()
    while time.time() - start < timeout:
        out = ssh(host, port,
            f"curl -s http://localhost:8188/history/{prompt_id}",
            check=False)
        try:
            hist = json.loads(out)
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                if outputs:
                    return outputs
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
    parser = argparse.ArgumentParser(description="Flux Image Generator (LoRA対応)")
    parser.add_argument("--host", required=True, help="RunPod IP")
    parser.add_argument("--port", required=True, type=int, help="RunPod SSH port")
    parser.add_argument("--prompts", required=True, help="プロンプトJSONファイル")
    parser.add_argument("--lora", default="", help="LoRAファイル名（例: flux_japanese_girl_v2.safetensors）")
    parser.add_argument("--lora-strength", default=0.8, type=float, help="LoRA強度（デフォルト: 0.8）")
    parser.add_argument("--steps", default=20, type=int, help="サンプリングステップ数")
    parser.add_argument("--width", default=768, type=int, help="画像幅")
    parser.add_argument("--height", default=1024, type=int, help="画像高さ")
    parser.add_argument("--seed", default=0, type=int, help="シード値（0=ランダム）")
    parser.add_argument("--output-dir", default="", help="出力先ディレクトリ（デフォルト: 作業中動画/）")
    args = parser.parse_args()

    # 出力先ディレクトリの上書き
    global LOCAL_OUTPUT_DIR
    if args.output_dir:
        LOCAL_OUTPUT_DIR = args.output_dir
        os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    # ── 接続確認 ──
    print(f"RunPodに接続中: {args.host}:{args.port}")
    if not check_comfyui(args.host, args.port):
        print("ComfyUIが起動していません", file=sys.stderr)
        sys.exit(1)
    print("ComfyUI: OK")

    if args.lora:
        print(f"LoRA: {args.lora} (strength={args.lora_strength})")

    # ── プロンプト読み込み ──
    with open(args.prompts) as f:
        prompts = json.load(f)

    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    # ── 生成ループ ──
    results = []
    for i, item in enumerate(prompts, 1):
        cut_id = item.get("id", f"C{i:02d}")
        prompt_text = item["prompt"]
        prefix = f"flux_{cut_id}"
        local_file = os.path.join(LOCAL_OUTPUT_DIR, f"flux_{cut_id}.png")

        if os.path.exists(local_file):
            print(f"\n[{cut_id}] スキップ（既存ファイルあり）: {local_file}")
            results.append({"id": cut_id, "file": local_file, "status": "skipped"})
            continue

        print(f"\n[{cut_id}] 生成開始 ({i}/{len(prompts)})")
        print(f"  プロンプト: {prompt_text[:80]}...")

        seed = args.seed if args.seed > 0 else random.randint(1, 2**32)
        wf = build_workflow(
            prompt_text, prefix,
            args.width, args.height, args.steps, seed,
            lora_name=args.lora if args.lora else None,
            lora_strength=args.lora_strength
        )

        # C08は商品写真なのでLoRAなし
        if cut_id == "C08" and args.lora:
            print("  (商品写真: LoRAなしで生成)")
            wf = build_workflow(
                prompt_text, prefix,
                args.width, args.height, args.steps, seed,
                lora_name=None
            )

        prompt_id = submit_workflow(args.host, args.port, wf)
        if not prompt_id:
            print(f"  [エラー] ワークフロー投入失敗", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})
            continue

        print(f"  prompt_id: {prompt_id}")
        outputs = poll_until_done(args.host, args.port, prompt_id)

        if not outputs:
            print(f"  [エラー] タイムアウト", file=sys.stderr)
            results.append({"id": cut_id, "status": "timeout"})
            continue

        remote_file = find_output_file(args.host, args.port, prefix)
        if not remote_file:
            print(f"  [エラー] 出力ファイルが見つかりません", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})
            continue

        ok = scp_download(args.host, args.port, remote_file, local_file)
        if ok:
            print(f"  ダウンロード完了: {local_file}")
            results.append({"id": cut_id, "file": local_file, "status": "ok"})
        else:
            print(f"  [エラー] ダウンロード失敗", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})

    # ── 結果サマリー ──
    print("\n" + "=" * 50)
    print("生成完了サマリー")
    print("=" * 50)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skip_count = sum(1 for r in results if r["status"] == "skipped")
    err_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    print(f"成功: {ok_count}  スキップ: {skip_count}  エラー: {err_count}")
    for r in results:
        icon = {"ok": "OK", "skipped": "SKIP", "error": "ERR", "timeout": "TIMEOUT"}.get(r["status"], "?")
        print(f"  [{icon}] {r['id']}: {r.get('file', r['status'])}")


if __name__ == "__main__":
    main()

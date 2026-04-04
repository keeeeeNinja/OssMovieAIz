#!/usr/bin/env python3
"""
Flux Image Generator via ComfyUI on RunPod

Usage:
  python3 scripts/generate_flux_images.py \
    --host IP --port PORT \
    --prompts scripts/flux_prompts.json \
    [--model flux1-dev.safetensors] \
    [--steps 20] \
    [--width 576] [--height 1024]

prompts JSON format:
  [
    {"id": "C1", "prompt": "A beautiful Japanese woman..."},
    {"id": "C2", "prompt": "..."},
    ...
  ]

Output: 作業中動画/flux_C01.png, flux_C02.png, ...
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time

SSH_KEY = os.path.expanduser("~/.ssh/runpod_key")
COMFYUI_OUTPUT_DIR = "/workspace/runpod-slim/ComfyUI/output"
LOCAL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../作業中動画")
WORKFLOW_TEMPLATE = os.path.join(os.path.dirname(__file__), "flux_workflow_template.json")


def ssh(host, port, cmd, check=True):
    full_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
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
    out = ssh(host, port, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/", check=False)
    return out.strip() == "200"


def list_flux_models(host, port):
    """RunPod上のFluxモデルファイルを一覧表示する"""
    out = ssh(host, port,
        "find /workspace/ComfyUI/models -name '*.safetensors' -o -name '*.gguf' 2>/dev/null | grep -i flux | head -20",
        check=False)
    return out


def submit_workflow(host, port, workflow: dict) -> str:
    """ComfyUI APIにワークフローを投入してprompt_idを返す"""
    payload = json.dumps({"prompt": workflow})
    # ローカルに一時ファイルを作成してSCPで転送、curlで投入
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload)
        tmp_local = f.name
    tmp_remote = "/tmp/comfy_payload.json"
    scp_cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", str(port), "-i", SSH_KEY,
        tmp_local, f"root@{host}:{tmp_remote}"
    ]
    subprocess.run(scp_cmd, capture_output=True)
    os.unlink(tmp_local)
    cmd = f"curl -s -X POST http://localhost:8188/prompt -H 'Content-Type: application/json' -d @{tmp_remote}"
    out = ssh(host, port, cmd)
    try:
        resp = json.loads(out)
        return resp.get("prompt_id", "")
    except Exception:
        print(f"Workflow submit error: {out}", file=sys.stderr)
        return ""


def poll_until_done(host, port, prompt_id: str, timeout=600):
    """生成完了を待つ（最大timeout秒）"""
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
                    return True
        except Exception:
            pass
        print("  生成中... (60秒後に再確認)", flush=True)
        time.sleep(60)
    return False


def find_output_file(host, port, prefix: str) -> str:
    """出力ファイルのパスを取得する"""
    out = ssh(host, port,
        f"ls -t {COMFYUI_OUTPUT_DIR}/{prefix}*.png 2>/dev/null | head -1",
        check=False)
    return out.strip()


def build_workflow(template: str, prompt: str, prefix: str, model: str,
                   clip_t5: str, clip_l: str, vae: str,
                   width: int, height: int, steps: int, seed: int = 0) -> dict:
    """テンプレートのプレースホルダーを置換してワークフローを生成する"""
    wf_str = template
    wf_str = wf_str.replace("[MODEL_NAME]", model)
    wf_str = wf_str.replace("[CLIP_T5]", clip_t5)
    wf_str = wf_str.replace("[CLIP_L]", clip_l)
    wf_str = wf_str.replace("[VAE_NAME]", vae)
    wf_str = wf_str.replace('"[PROMPT]"', json.dumps(prompt))
    wf_str = wf_str.replace("[WIDTH]", str(width))
    wf_str = wf_str.replace("[HEIGHT]", str(height))
    wf_str = wf_str.replace("[SEED]", str(seed))
    wf_str = wf_str.replace("[STEPS]", str(steps))
    wf_str = wf_str.replace("[OUTPUT_PREFIX]", prefix)
    return json.loads(wf_str)


def main():
    parser = argparse.ArgumentParser(description="Flux Image Generator via ComfyUI on RunPod")
    parser.add_argument("--host", required=True, help="RunPod IP")
    parser.add_argument("--port", required=True, type=int, help="RunPod SSH port")
    parser.add_argument("--prompts", required=True, help="プロンプトJSONファイルのパス")
    parser.add_argument("--model", default="", help="Fluxモデルファイル名（省略時は自動検出）")
    parser.add_argument("--clip-t5", default="t5xxl_fp16.safetensors", help="T5XXL CLIPファイル名")
    parser.add_argument("--clip-l", default="clip_l.safetensors", help="CLIP-Lファイル名")
    parser.add_argument("--vae", default="ae.safetensors", help="VAEファイル名")
    parser.add_argument("--steps", default=20, type=int, help="サンプリングステップ数")
    parser.add_argument("--width", default=576, type=int, help="画像幅（縦型: 576）")
    parser.add_argument("--height", default=1024, type=int, help="画像高さ（縦型: 1024）")
    parser.add_argument("--seed", default=0, type=int, help="シード値（0=ランダム）")
    args = parser.parse_args()

    # ── 接続確認 ──────────────────────────────
    print(f"RunPodに接続中: {args.host}:{args.port}")
    gpu_info = ssh(args.host, args.port, "nvidia-smi | grep -E 'GPU|MiB' | head -3")
    print(f"GPU: {gpu_info}")

    if not check_comfyui(args.host, args.port):
        print("ComfyUIが起動していません。起動します...")
        ssh(args.host, args.port,
            "cd /workspace/ComfyUI && nohup python3 main.py --listen 0.0.0.0 --port 8188 --use-sage-attention > /workspace/comfyui.log 2>&1 &")
        print("30秒待機...")
        time.sleep(30)
        if not check_comfyui(args.host, args.port):
            print("ComfyUI起動失敗。ログを確認してください。", file=sys.stderr)
            sys.exit(1)
    print("ComfyUI: OK")

    # ── モデル確認 ────────────────────────────
    if not args.model:
        print("\n利用可能なFluxモデル:")
        models = list_flux_models(args.host, args.port)
        print(models)
        print("\n--model オプションでモデルファイル名を指定して再実行してください。")
        sys.exit(0)

    # ── ワークフローテンプレート読み込み ──────────
    with open(WORKFLOW_TEMPLATE) as f:
        template = f.read()  # 文字列として読み込み（プレースホルダーがあるためJSONパース前）

    # ── プロンプト読み込み ─────────────────────
    with open(args.prompts) as f:
        prompts = json.load(f)

    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    # ── 生成ループ ────────────────────────────
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
        print(f"  プロンプト: {prompt_text[:60]}...")

        seed = args.seed if args.seed > 0 else random.randint(1, 2**32)
        wf = build_workflow(
            template, prompt_text, prefix,
            args.model, args.clip_t5, args.clip_l, args.vae,
            args.width, args.height, args.steps, seed
        )

        prompt_id = submit_workflow(args.host, args.port, wf)
        if not prompt_id:
            print(f"  [エラー] ワークフロー投入失敗", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})
            continue

        print(f"  prompt_id: {prompt_id}")
        done = poll_until_done(args.host, args.port, prompt_id, timeout=600)

        if not done:
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
            print(f"  ✅ ダウンロード完了: {local_file}")
            results.append({"id": cut_id, "file": local_file, "status": "ok"})
        else:
            print(f"  [エラー] ダウンロード失敗", file=sys.stderr)
            results.append({"id": cut_id, "status": "error"})

    # ── 結果サマリー ──────────────────────────
    print("\n" + "=" * 50)
    print("生成完了サマリー")
    print("=" * 50)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skip_count = sum(1 for r in results if r["status"] == "skipped")
    err_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    print(f"✅ 成功: {ok_count}  ⏭ スキップ: {skip_count}  ❌ エラー: {err_count}")
    for r in results:
        icon = {"ok": "✅", "skipped": "⏭", "error": "❌", "timeout": "⏱"}.get(r["status"], "?")
        print(f"  {icon} {r['id']}: {r.get('file', r['status'])}")


if __name__ == "__main__":
    main()

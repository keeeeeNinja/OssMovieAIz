#!/usr/bin/env python3
"""
RunPod Serverless ComfyUI request submitter.

既存 generate_flux_images.py / generate_wan_i2v.py の役割を Serverless 版で置き換える。
- 通信先: https://api.runpod.ai/v2/{endpoint_id}/run
- ロック機構（fcntl）と T{N}_C{NN} ルーティングは流用
- 完了 job は job_map_{flux,i2v}.json に追記。fetch スクリプトが参照する

Usage:
  # Flux 静止画
  python3 scripts/serverless_request.py \\
    --endpoint flux \\
    --prompts scripts/flux_prompts.json \\
    --output-root 作業中動画 \\
    --lora flux_japanese_girl_v2.safetensors

  # Wan I2V
  python3 scripts/serverless_request.py \\
    --endpoint i2v \\
    --prompts scripts/wan_i2v_prompts.json \\
    --output-root 作業中動画
"""

import argparse
import fcntl
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import shutil

from dotenv import load_dotenv
load_dotenv(override=True)

API_BASE = "https://api.runpod.ai/v2"
WORKFLOWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serverless_workflows")
THEME_PREFIX_RE = re.compile(r"^T(\d+)_")
LOCK_DIR_BASE = ".locks_serverless"


def theme_dir_from_id(cut_id, root):
    m = THEME_PREFIX_RE.match(cut_id)
    if m:
        return os.path.join(root, f"theme{m.group(1)}")
    return root


def try_lock(cut_id, lock_dir):
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, f"{cut_id}.lock")
    try:
        f = open(lock_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(f"{os.getpid()}\n")
        f.flush()
        return True, f
    except (OSError, IOError):
        return False, None


def release_lock(lock_file):
    if lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass


def load_template(name):
    path = os.path.join(WORKFLOWS_DIR, f"{name}.json")
    with open(path) as f:
        return json.load(f)


def apply_placeholders(workflow, replacements):
    """workflow JSON 内のプレースホルダ文字列を再帰的に置換する。
    "[PROMPT]" などの文字列値は置換、整数フィールドは int 型へ自動変換。"""
    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items() if k != "_comment"}
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, str):
            if obj in replacements:
                return replacements[obj]
            for key, val in replacements.items():
                obj = obj.replace(key, str(val))
            return obj
        return obj
    return walk(workflow)


def build_flux_workflow(item, args):
    template_name = "flux_lora" if args.lora else "flux"
    wf = load_template(template_name)
    seed = args.seed if args.seed else (int(time.time() * 1000) ^ os.getpid()) & 0xFFFFFFFF
    replacements = {
        "[PROMPT]": item["prompt"],
        "[WIDTH]": int(args.width),
        "[HEIGHT]": int(args.height),
        "[SEED]": int(seed),
        "[STEPS]": int(args.steps),
        "[OUTPUT_PREFIX]": f"flux_{item['id']}",
    }
    if args.lora:
        replacements["[LORA_NAME]"] = args.lora
        replacements["[LORA_STRENGTH]"] = float(args.lora_strength)
    return apply_placeholders(wf, replacements)


def build_i2v_workflow(item, args):
    wf = load_template("wan_i2v")
    seed = args.seed if args.seed else (int(time.time() * 1000) ^ os.getpid()) & 0xFFFFFFFF
    image_name = item.get("image") or f"flux_{item['id']}.png"
    replacements = {
        "[PROMPT]": item["prompt"],
        "[NEGATIVE]": item.get("negative", "blurry, low quality, deformed, bad anatomy"),
        "[IMAGE_NAME]": image_name,
        "[SEED_VALUE]": int(seed),
        "[WIDTH]": int(args.width),
        "[HEIGHT]": int(args.height),
        "[COEFFICIENTS]": item.get("coefficients", "i2v_480"),
        "[OUTPUT_PREFIX]": f"scene_{item['id']}_wan21",
    }
    return apply_placeholders(wf, replacements)


def http_post_json(url, payload, headers):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={**headers, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {body}")


def http_get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {body}")


def submit_job(endpoint_id, api_key, workflow):
    url = f"{API_BASE}/{endpoint_id}/run"
    payload = {"input": {"workflow": workflow}}
    return http_post_json(url, payload, {"Authorization": f"Bearer {api_key}"})


def poll_job(endpoint_id, api_key, job_id, timeout=900):
    url = f"{API_BASE}/{endpoint_id}/status/{job_id}"
    start = time.time()
    last_status = ""
    while time.time() - start < timeout:
        resp = http_get_json(url, {"Authorization": f"Bearer {api_key}"})
        status = resp.get("status", "")
        if status == "COMPLETED":
            return resp
        if status in ("FAILED", "CANCELLED", "TIMED_OUT"):
            raise RuntimeError(f"Job {job_id} {status}: {resp}")
        elapsed = int(time.time() - start)
        if status != last_status:
            print(f"  [{job_id[:8]}] {status} ({elapsed}s)", flush=True)
            last_status = status
        time.sleep(8)
    raise TimeoutError(f"Job {job_id} timeout after {timeout}s")


def append_job_map(output_root, endpoint, entry):
    path = os.path.join(output_root, f"job_map_{endpoint}.json")
    existing = []
    if os.path.exists(path):
        with open(path) as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    existing.append(entry)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", choices=["flux", "i2v"], required=True)
    parser.add_argument("--endpoint-id", default="",
                        help="未指定なら環境変数 RUNPOD_ENDPOINT_FLUX / RUNPOD_ENDPOINT_I2V を参照")
    parser.add_argument("--api-key", default=os.environ.get("RUNPOD_API_KEY", ""))
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output-root", default="作業中動画")
    parser.add_argument("--scenes", default="")
    parser.add_argument("--lora", default="")
    parser.add_argument("--lora-strength", type=float, default=0.8)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--clean-locks", action="store_true")
    args = parser.parse_args()

    if not args.endpoint_id:
        env = "RUNPOD_ENDPOINT_FLUX" if args.endpoint == "flux" else "RUNPOD_ENDPOINT_I2V"
        args.endpoint_id = os.environ.get(env, "")
    if not args.endpoint_id:
        sys.exit(f"❌ --endpoint-id か環境変数 RUNPOD_ENDPOINT_{args.endpoint.upper()} を指定してください")
    if not args.api_key:
        sys.exit("❌ --api-key か環境変数 RUNPOD_API_KEY を設定してください")

    if args.lora and "ayano" in args.lora.lower():
        if args.lora_strength == 0.8:
            args.lora_strength = 0.85
            print("  (Ayano_Chan LoRA 検出 → strength=0.85)")

    with open(args.prompts) as f:
        prompts = json.load(f)
    if args.scenes:
        keep = set(s.strip() for s in args.scenes.split(","))
        prompts = [p for p in prompts if p.get("id") in keep]
        if not prompts:
            sys.exit(f"⚠️  --scenes に該当するプロンプトがありません")

    os.makedirs(args.output_root, exist_ok=True)
    lock_dir = os.path.join(args.output_root, f"{LOCK_DIR_BASE}_{args.endpoint}")
    if args.clean_locks:
        shutil.rmtree(lock_dir, ignore_errors=True)
        print(f"ロックディレクトリを削除: {lock_dir}")

    builder = build_flux_workflow if args.endpoint == "flux" else build_i2v_workflow
    print(f"Endpoint: {args.endpoint} ({args.endpoint_id})")
    print(f"対象シーン: {[p['id'] for p in prompts]}")

    completed = 0
    failed = 0
    for item in prompts:
        cut_id = item["id"]
        ok, lock_file = try_lock(cut_id, lock_dir)
        if not ok:
            print(f"  [{cut_id}] 他プロセスが処理中、スキップ")
            continue
        try:
            wf = builder(item, args)
            print(f"\n[{cut_id}] 投入...")
            resp = submit_job(args.endpoint_id, args.api_key, wf)
            job_id = resp.get("id", "")
            if not job_id:
                print(f"  ❌ submit 失敗: {resp}")
                failed += 1
                continue
            print(f"  job_id={job_id}")
            try:
                result = poll_job(args.endpoint_id, args.api_key, job_id, timeout=args.timeout)
            except (RuntimeError, TimeoutError) as e:
                print(f"  ❌ {e}")
                failed += 1
                continue
            entry = {
                "scene_id": cut_id,
                "endpoint": args.endpoint,
                "job_id": job_id,
                "theme_dir": theme_dir_from_id(cut_id, args.output_root),
                "execution_time_ms": result.get("executionTime"),
                "delay_time_ms": result.get("delayTime"),
            }
            append_job_map(args.output_root, args.endpoint, entry)
            print(f"  ✅ 完了 (exec {result.get('executionTime', '?')}ms / delay {result.get('delayTime', '?')}ms)")
            completed += 1
        finally:
            release_lock(lock_file)

    print(f"\n結果: 成功 {completed} / 失敗 {failed} / 合計 {len(prompts)}")
    print(f"job_map: {args.output_root}/job_map_{args.endpoint}.json")
    print(f"次に: python3 scripts/serverless_fetch.py --endpoint {args.endpoint} --output-root {args.output_root}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Flux Image Generator via ComfyUI on RunPod (LoRA対応 / ロックベース分散)

Usage:
  # 単体（単一テーマ）
  python3 scripts/generate_flux_images.py \
    --host IP --port PORT \
    --prompts scripts/flux_prompts.json \
    --output-dir 作業中動画/theme1 \
    [--lora flux_japanese_girl_v2.safetensors] \
    [--copy-to-input]

  # 並列プール（マルチテーマ・全Podが全シーンを受け取り、ロックで自動分配）
  python3 scripts/generate_flux_images.py \
    --host pod1_ip --port pod1_port \
    --prompts scripts/flux_prompts.json \
    --output-root 作業中動画 \
    --lora flux_japanese_girl_v2.safetensors \
    --copy-to-input &
  python3 scripts/generate_flux_images.py \
    --host pod2_ip --port pod2_port \
    --prompts scripts/flux_prompts.json \
    --output-root 作業中動画 \
    --lora flux_japanese_girl_v2.safetensors \
    --copy-to-input &

--output-root を指定するとシーンIDの先頭（T1_/T2_/...）から
テーマフォルダを自動ルーティングする（T1_C03 → 作業中動画/theme1/flux_T1_C03.png）。
同じフォルダにロックディレクトリ .locks_flux/ を作り、複数Pod間で未着手シーンを取り合う。
テーマプレフィックスが無いIDは output-root 直下に保存する。

--scenes:
  プロンプトJSONから指定したidだけを対象にする。並列プール運用時は通常は指定しない
  （全シーンを渡してロックで分配するのが推奨）。

--copy-to-input:
  生成完了後に on-pod で /workspace/ComfyUI/output/flux_*.png を
  /workspace/ComfyUI/input/ にコピーする。同じPodでそのままWan I2Vを
  実行するときに使う（再アップロードが不要になる）。
"""

import argparse
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import time

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
COMFYUI_OUTPUT_DIR = "/workspace/ComfyUI/output"
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../作業中動画")
LOCAL_OUTPUT_DIR = DEFAULT_OUTPUT_DIR  # --output-dir で上書き
OUTPUT_ROOT = ""  # --output-root で設定（空文字なら単一ディレクトリモード）
LOCK_DIR = os.path.join(DEFAULT_OUTPUT_DIR, ".locks_flux")

THEME_PREFIX_RE = re.compile(r"^T(\d+)_")


def theme_dir_from_id(cut_id, root):
    """シーンIDの T{N}_ プレフィックスから theme{N} フォルダを返す。
    プレフィックスが無ければ root 直下。"""
    m = THEME_PREFIX_RE.match(cut_id)
    if m:
        return os.path.join(root, f"theme{m.group(1)}")
    return root


def resolve_local_file(cut_id):
    """そのシーンの最終的なローカルpngパスを返す"""
    if OUTPUT_ROOT:
        return os.path.join(theme_dir_from_id(cut_id, OUTPUT_ROOT), f"flux_{cut_id}.png")
    return os.path.join(LOCAL_OUTPUT_DIR, f"flux_{cut_id}.png")


def try_lock(cut_id):
    """シーンのロックを取得する。取れたらTrueとファイルオブジェクト"""
    os.makedirs(LOCK_DIR, exist_ok=True)
    lock_path = os.path.join(LOCK_DIR, f"{cut_id}.lock")
    try:
        f = open(lock_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(f"{os.getpid()}\n")
        f.flush()
        return True, f
    except (OSError, IOError):
        return False, None


def release_lock(cut_id, lock_file):
    if lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass
    lock_path = os.path.join(LOCK_DIR, f"{cut_id}.lock")
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass


def cleanup_locks():
    if os.path.exists(LOCK_DIR):
        for f in os.listdir(LOCK_DIR):
            if f.endswith(".lock"):
                try:
                    os.unlink(os.path.join(LOCK_DIR, f))
                except Exception:
                    pass


def auto_cleanup_stale_locks():
    """60秒以上前のロックで、プロセスが死んでいるものを削除する"""
    if not os.path.exists(LOCK_DIR):
        return
    now = time.time()
    for lf in os.listdir(LOCK_DIR):
        if not lf.endswith(".lock"):
            continue
        lp = os.path.join(LOCK_DIR, lf)
        try:
            if now - os.path.getmtime(lp) > 60:
                try:
                    f = open(lp, "r+")
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
                    f.close()
                    os.unlink(lp)
                    print(f"  古いロックを削除: {lf}")
                except (OSError, IOError):
                    pass
        except Exception:
            pass


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
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
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


def poll_until_done(host, port, prompt_id, timeout=600):
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
    parser = argparse.ArgumentParser(description="Flux Image Generator (LoRA対応 / ロックベース分散)")
    parser.add_argument("--host", required=True, help="RunPod IP")
    parser.add_argument("--port", required=True, type=int, help="RunPod SSH port")
    parser.add_argument("--prompts", required=True, help="プロンプトJSONファイル")
    parser.add_argument("--lora", default="", help="LoRAファイル名")
    parser.add_argument("--lora-strength", default=None, type=float, help="LoRA強度")
    parser.add_argument("--steps", default=20, type=int)
    parser.add_argument("--width", default=768, type=int)
    parser.add_argument("--height", default=1024, type=int)
    parser.add_argument("--seed", default=0, type=int)
    parser.add_argument("--output-dir", default="",
                        help="出力先ディレクトリ（単一テーマ用）。--output-root と排他")
    parser.add_argument("--output-root", default="",
                        help="並列プールモードのルートディレクトリ。シーンIDのT{N}_プレフィックスから theme{N}/ へ自動ルーティング")
    parser.add_argument("--scenes", default="",
                        help="対象シーンIDをカンマ区切り。並列プール運用時は通常は省略（全シーンを渡してロック分配）")
    parser.add_argument("--copy-to-input", action="store_true",
                        help="生成後に on-pod で output/ → input/ にコピー")
    parser.add_argument("--clean-locks", action="store_true",
                        help="開始前にロックファイルを全削除")
    args = parser.parse_args()

    if args.lora_strength is None:
        if args.lora and "ayano_chan" in args.lora.lower():
            args.lora_strength = 0.85
            print(f"  (Ayano_Chan LoRA検出 → strength=0.85 を自動適用)")
        else:
            args.lora_strength = 0.8

    global LOCAL_OUTPUT_DIR, OUTPUT_ROOT, LOCK_DIR
    if args.output_root and args.output_dir:
        print("❌ --output-root と --output-dir は同時指定できません", file=sys.stderr)
        sys.exit(1)
    if args.output_root:
        OUTPUT_ROOT = args.output_root
        LOCK_DIR = os.path.join(OUTPUT_ROOT, ".locks_flux")
        os.makedirs(OUTPUT_ROOT, exist_ok=True)
    elif args.output_dir:
        LOCAL_OUTPUT_DIR = args.output_dir
        LOCK_DIR = os.path.join(LOCAL_OUTPUT_DIR, ".locks_flux")
        os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    else:
        LOCK_DIR = os.path.join(LOCAL_OUTPUT_DIR, ".locks_flux")

    print(f"RunPodに接続中: {args.host}:{args.port}")
    if not check_comfyui(args.host, args.port):
        print("ComfyUIが起動していません", file=sys.stderr)
        sys.exit(1)
    print("ComfyUI: OK")

    if args.lora:
        print(f"LoRA: {args.lora} (strength={args.lora_strength})")
    if OUTPUT_ROOT:
        print(f"プールモード: output-root={OUTPUT_ROOT}, lock={LOCK_DIR}")
    else:
        print(f"単体モード: output-dir={LOCAL_OUTPUT_DIR}")

    with open(args.prompts) as f:
        prompts = json.load(f)

    if args.scenes:
        scene_filter = set(s.strip() for s in args.scenes.split(","))
        prompts = [p for p in prompts if p.get("id") in scene_filter]
        print(f"対象シーン: {[p.get('id') for p in prompts]}")
        if not prompts:
            print("⚠️  フィルタに合致するシーンがありません", file=sys.stderr)
            sys.exit(1)

    if args.clean_locks:
        cleanup_locks()
        print("ロックファイルを削除しました")

    auto_cleanup_stale_locks()

    def run_generation_pass(prompts_list, pass_num):
        pass_results = []
        lock_files = {}
        try:
            for i, item in enumerate(prompts_list, 1):
                cut_id = item.get("id", f"C{i:02d}")
                prompt_text = item["prompt"]
                prefix = f"flux_{cut_id}"
                local_file = resolve_local_file(cut_id)
                os.makedirs(os.path.dirname(local_file), exist_ok=True)

                if os.path.exists(local_file):
                    if pass_num == 1:
                        print(f"\n[{cut_id}] スキップ（既存ファイルあり）")
                    pass_results.append({"id": cut_id, "file": local_file, "status": "skipped"})
                    continue

                locked, lock_file = try_lock(cut_id)
                if not locked:
                    if pass_num == 1:
                        print(f"\n[{cut_id}] スキップ（別Podが生成中）")
                    pass_results.append({"id": cut_id, "status": "skipped_by_other"})
                    continue
                lock_files[cut_id] = lock_file

                if os.path.exists(local_file):
                    print(f"\n[{cut_id}] スキップ（別Podが完了済み）")
                    pass_results.append({"id": cut_id, "file": local_file, "status": "skipped"})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                label = f"({pass_num}周目)" if pass_num > 1 else ""
                print(f"\n[{cut_id}] 生成開始 {label}({i}/{len(prompts_list)})")
                print(f"  プロンプト: {prompt_text[:80]}...")

                seed = args.seed if args.seed > 0 else random.randint(1, 2**32)
                use_lora = args.lora
                # C08 のような商品写真は LoRA なし
                if cut_id.endswith("C08") and use_lora:
                    print("  (商品写真: LoRAなしで生成)")
                    use_lora = ""

                wf = build_workflow(
                    prompt_text, prefix,
                    args.width, args.height, args.steps, seed,
                    lora_name=use_lora if use_lora else None,
                    lora_strength=args.lora_strength
                )

                prompt_id = submit_workflow(args.host, args.port, wf)
                if not prompt_id:
                    print(f"  [エラー] ワークフロー投入失敗", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "error"})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                print(f"  prompt_id: {prompt_id}")
                outputs = poll_until_done(args.host, args.port, prompt_id)

                if not outputs:
                    print(f"  [エラー] タイムアウト", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "timeout"})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                remote_file = find_output_file(args.host, args.port, prefix)
                if not remote_file:
                    print(f"  [エラー] 出力ファイルが見つかりません", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "error"})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                ok = scp_download(args.host, args.port, remote_file, local_file)
                if ok:
                    print(f"  ダウンロード完了: {local_file}")
                    pass_results.append({"id": cut_id, "file": local_file, "status": "ok"})
                else:
                    print(f"  [エラー] ダウンロード失敗", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "error"})

                release_lock(cut_id, lock_file)
                del lock_files[cut_id]
        finally:
            for cid, lf in lock_files.items():
                release_lock(cid, lf)

        return pass_results

    # ── 1周目 ──
    results = run_generation_pass(prompts, 1)

    # ── 2周目: 別Podに任せたが未完了のシーンを拾う ──
    skipped_other_ids = {r["id"] for r in results if r["status"] == "skipped_by_other"}
    if skipped_other_ids:
        time.sleep(10)
        retry_prompts = []
        for item in prompts:
            if item["id"] in skipped_other_ids:
                if not os.path.exists(resolve_local_file(item["id"])):
                    retry_prompts.append(item)
        if retry_prompts:
            print(f"\n--- 2周目: 未完了 {len(retry_prompts)} シーンをリトライ ---")
            retry_results = run_generation_pass(retry_prompts, 2)
            retry_map = {r["id"]: r for r in retry_results}
            results = [retry_map.get(r["id"], r) if r["status"] == "skipped_by_other" else r for r in results]

    # ── on-pod コピー: output/ → input/ ──
    if args.copy_to_input:
        ok_ids = [r["id"] for r in results if r["status"] in ("ok", "skipped")]
        if ok_ids:
            print(f"\non-pod で flux_*.png を output/ → input/ にコピー中 ({len(ok_ids)}件)...")
            ssh(args.host, args.port,
                "mkdir -p /workspace/ComfyUI/input && cp -f /workspace/ComfyUI/output/flux_*.png /workspace/ComfyUI/input/ 2>&1 || true",
                check=False)
            listed = ssh(args.host, args.port,
                         "ls /workspace/ComfyUI/input/flux_*.png 2>/dev/null | wc -l",
                         check=False)
            print(f"  input/ 内の flux_*.png: {listed} 件")

    # ── サマリー ──
    print("\n" + "=" * 50)
    print("Flux 生成完了サマリー")
    print("=" * 50)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skip_count = sum(1 for r in results if r["status"] in ("skipped", "skipped_by_other"))
    other_count = sum(1 for r in results if r["status"] == "skipped_by_other")
    err_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    print(f"成功: {ok_count}  スキップ: {skip_count}（うち別Pod: {other_count}）  エラー: {err_count}")
    for r in results:
        icon = {"ok": "OK", "skipped": "SKIP", "skipped_by_other": "OTHER", "error": "ERR", "timeout": "TIMEOUT"}.get(r["status"], "?")
        print(f"  [{icon}] {r['id']}: {r.get('file', r['status'])}")


if __name__ == "__main__":
    main()

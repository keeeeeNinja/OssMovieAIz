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
import base64
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
from pathlib import Path

_env_path = Path.cwd() / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

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
    if args.template:
        template_name = args.template
    elif args.lora:
        template_name = "flux_lora"
    else:
        template_name = "flux"
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


def build_acestep_input(item, args):
    """ACE-Step は ComfyUI ではないので handler に直接 dict を渡す。"""
    inp = {
        "caption": item.get("caption") or args.ace_caption or args.prompt_text,
        "duration": int(item.get("duration") or args.ace_duration),
        "bpm": int(item.get("bpm") or args.ace_bpm),
        "lyrics": item.get("lyrics") or args.ace_lyrics or "",
        "variant": item.get("variant") or args.ace_variant,
    }
    seed = item.get("seed") if item.get("seed") is not None else args.ace_seed
    if seed is not None:
        inp["seed"] = int(seed)
    if not inp["caption"]:
        raise ValueError("--ace-caption または --prompt-text が必要")
    return inp


def build_tts_input(item, args):
    """TTS は ComfyUI ではないので workflow JSON を持たない。handler が直接受け取る dict を返す。"""
    mode = item.get("mode") or args.tts_mode
    inp = {
        "mode": mode,
        "text": item.get("text") or args.prompt_text or item.get("prompt", ""),
        "language": item.get("language") or args.tts_language,
    }
    if mode == "clone":
        ref_path = item.get("ref_audio") or args.tts_ref_audio
        ref_text = item.get("ref_text") or args.tts_ref_text
        if not ref_path or not os.path.isfile(ref_path):
            raise ValueError(f"--tts-ref-audio が必要 (clone mode): {ref_path}")
        if not ref_text:
            raise ValueError("--tts-ref-text が必要 (clone mode)")
        inp["ref_audio"] = encode_image_file(ref_path)  # base64 (関数名は image だが汎用)
        inp["ref_text"] = ref_text
    elif mode == "preset":
        inp["speaker"] = item.get("speaker") or args.tts_speaker
    elif mode == "design":
        inp["instruct"] = item.get("instruct") or args.tts_instruct
    else:
        raise ValueError(f"unknown tts mode: {mode}")
    # サンプリング系（任意）
    for k in ("do_sample", "top_k", "top_p", "temperature", "repetition_penalty"):
        if hasattr(args, f"tts_{k}") and getattr(args, f"tts_{k}") is not None:
            inp[k] = getattr(args, f"tts_{k}")
    return inp


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


def encode_image_file(path):
    """ローカル画像を base64 (Data URI 不要、純粋な base64 文字列) でエンコード"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def submit_job(endpoint_id, api_key, workflow, images=None, raw_input=None):
    """ComfyUI 系: workflow / images を input.workflow / input.images で投げる。
    TTS 系: raw_input が指定されれば input にそのまま展開する（workflow を持たない）。"""
    url = f"{API_BASE}/{endpoint_id}/run"
    if raw_input is not None:
        inp = raw_input
    else:
        inp = {"workflow": workflow}
        if images:
            inp["images"] = images
    payload = {"input": inp}
    return http_post_json(url, payload, {"Authorization": f"Bearer {api_key}"})


def save_outputs(result, dest_dir, scene_id):
    """job 完了結果から base64 出力を decode してローカル保存。
    対応形式:
      ComfyUI: output.images = [{"filename":"xxx.png","data":"<b64>"}]
      Wan I2V: output.videos / output.files
      Qwen3-TTS: output.audio (str), output.sample_rate, output.duration_sec
    返り値: 保存したパスのリスト"""
    os.makedirs(dest_dir, exist_ok=True)
    out = result.get("output") or {}
    saved = []
    # images キー (Flux など)
    for item in out.get("images", []) or []:
        data = item.get("data") or item.get("image") or ""
        filename = item.get("filename") or f"{scene_id}.png"
        if not data:
            continue
        local = os.path.join(dest_dir, filename)
        with open(local, "wb") as f:
            f.write(base64.b64decode(data))
        saved.append(local)
    # videos / files キー (Wan I2V 用、handler によっては files キー)
    for k in ("videos", "files"):
        for item in out.get(k, []) or []:
            data = item.get("data") or ""
            filename = item.get("filename") or f"{scene_id}.bin"
            if not data:
                continue
            local = os.path.join(dest_dir, filename)
            with open(local, "wb") as f:
                f.write(base64.b64decode(data))
            saved.append(local)
    # audio キー (Qwen3-TTS): output.audio が base64 文字列
    if isinstance(out.get("audio"), str) and out["audio"]:
        sr = out.get("sample_rate")
        dur = out.get("duration_sec")
        local = os.path.join(dest_dir, f"tts_{scene_id}.wav")
        with open(local, "wb") as f:
            f.write(base64.b64decode(out["audio"]))
        saved.append(local)
        if sr or dur:
            print(f"  🎙️  sample_rate={sr} duration={dur}s")
    return saved


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
    parser.add_argument("--endpoint", choices=["flux", "i2v", "tts", "acestep"], required=True)
    parser.add_argument("--endpoint-id", default="",
                        help="未指定なら環境変数 RUNPOD_ENDPOINT_FLUX / I2V / TTS / ACESTEP を参照")
    parser.add_argument("--api-key", default=os.environ.get("RUNPOD_API_KEY", ""))
    parser.add_argument("--prompts", required=False, default="",
                        help="プロンプト JSON。--prompt-text 単独使用時は不要")
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
    parser.add_argument("--template", default="",
                        help="serverless_workflows/ 配下のテンプレ名（拡張子なし）。"
                             "未指定なら lora あれば flux_lora、なければ flux を使用。"
                             "Schnell に切り替えるなら --template flux_schnell を指定")
    # --- TTS (Qwen3-TTS) 専用 ---
    parser.add_argument("--tts-mode", choices=["clone", "preset", "design"], default="clone")
    parser.add_argument("--tts-language", default="Japanese")
    parser.add_argument("--tts-ref-audio", default="",
                        help="clone mode: リファレンス wav のローカルパス（base64 で送信）")
    parser.add_argument("--tts-ref-text", default="",
                        help="clone mode: リファレンス wav の書き起こしテキスト")
    parser.add_argument("--tts-speaker", default="ono_anna",
                        help="preset mode: 話者名（aiden/ono_anna 等の9種）")
    parser.add_argument("--tts-instruct", default="",
                        help="design mode: 自然言語の声スタイル指示")
    # --- ACE-Step (BGM) 専用 ---
    parser.add_argument("--ace-caption", default="", help="ACE-Step: 曲スタイルの説明")
    parser.add_argument("--ace-duration", type=int, default=30, help="ACE-Step: 秒数 (10..600)")
    parser.add_argument("--ace-bpm", type=int, default=120, help="ACE-Step: BPM")
    parser.add_argument("--ace-lyrics", default="", help="ACE-Step: 歌詞（インストなら空）")
    parser.add_argument("--ace-variant", default="xl-turbo",
                        help="ACE-Step バリアント: xl-turbo / xl-base / xl-sft")
    parser.add_argument("--ace-seed", type=int, default=None)
    parser.add_argument("--tts-do-sample", type=int, default=None)
    parser.add_argument("--tts-top-k", type=int, default=None)
    parser.add_argument("--tts-top-p", type=float, default=None)
    parser.add_argument("--tts-temperature", type=float, default=None)
    parser.add_argument("--tts-repetition-penalty", type=float, default=None)
    parser.add_argument("--prompt-text", default="",
                        help="単発テスト用: id=TEST のシーンを 1 件作って実行")
    parser.add_argument("--negative-text", default="blurry, low quality, deformed, bad anatomy",
                        help="I2V のネガティブプロンプト (--prompt-text 単独使用時)")
    parser.add_argument("--image-file", default="",
                        help="I2V 用入力画像のローカルパス。base64 化して input.images で注入")
    parser.add_argument("--save-locally", action="store_true",
                        help="job 完了後、base64 出力を decode して output-root に保存")
    args = parser.parse_args()

    if not args.endpoint_id:
        env = {"flux": "RUNPOD_ENDPOINT_FLUX", "i2v": "RUNPOD_ENDPOINT_I2V",
               "tts": "RUNPOD_ENDPOINT_TTS",
               "acestep": "RUNPOD_ENDPOINT_ACESTEP"}[args.endpoint]
        args.endpoint_id = os.environ.get(env, "")
    if not args.endpoint_id:
        sys.exit(f"❌ --endpoint-id か環境変数 RUNPOD_ENDPOINT_{args.endpoint.upper()} を指定してください")
    if not args.api_key:
        sys.exit("❌ --api-key か環境変数 RUNPOD_API_KEY を設定してください")

    if args.lora and "ayano" in args.lora.lower():
        if args.lora_strength == 0.8:
            args.lora_strength = 0.85
            print("  (Ayano_Chan LoRA 検出 → strength=0.85)")

    if args.prompt_text and not args.prompts:
        # 単発テスト: 仮想シーン TEST を 1 件作る
        test_item = {"id": "TEST", "prompt": args.prompt_text}
        if args.endpoint == "i2v":
            test_item["negative"] = args.negative_text
            if args.image_file:
                test_item["image"] = os.path.basename(args.image_file)
        if args.endpoint == "tts":
            test_item["text"] = args.prompt_text
        prompts = [test_item]
    else:
        if not args.prompts:
            sys.exit("❌ --prompts または --prompt-text を指定してください")
        with open(args.prompts) as f:
            prompts = json.load(f)
        if args.scenes:
            keep = set(s.strip() for s in args.scenes.split(","))
            prompts = [p for p in prompts if p.get("id") in keep]
            if not prompts:
                sys.exit(f"⚠️  --scenes に該当するプロンプトがありません")
        # --prompt-text が指定されたら全シーンのプロンプトを上書き
        if args.prompt_text:
            for p in prompts:
                p["prompt"] = args.prompt_text

    os.makedirs(args.output_root, exist_ok=True)
    lock_dir = os.path.join(args.output_root, f"{LOCK_DIR_BASE}_{args.endpoint}")
    if args.clean_locks:
        shutil.rmtree(lock_dir, ignore_errors=True)
        print(f"ロックディレクトリを削除: {lock_dir}")

    builder = {
        "flux": build_flux_workflow,
        "i2v": build_i2v_workflow,
        "tts": build_tts_input,
        "acestep": build_acestep_input,
    }[args.endpoint]
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
            # --image-file が指定されていれば input.images に注入（ComfyUI 系のみ）
            images_payload = None
            if args.image_file and args.endpoint in ("flux", "i2v"):
                if not os.path.isfile(args.image_file):
                    print(f"  ❌ --image-file が存在しません: {args.image_file}")
                    failed += 1
                    continue
                images_payload = [{
                    "name": os.path.basename(args.image_file),
                    "image": encode_image_file(args.image_file),
                }]
            print(f"\n[{cut_id}] 投入...")
            if args.endpoint in ("tts", "acestep"):
                # raw input dict（ComfyUI workflow を持たない handler）
                resp = submit_job(args.endpoint_id, args.api_key, None, raw_input=wf)
            else:
                resp = submit_job(args.endpoint_id, args.api_key, wf, images=images_payload)
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
            if args.save_locally:
                dest = theme_dir_from_id(cut_id, args.output_root)
                saved = save_outputs(result, dest, cut_id)
                if saved:
                    for p in saved:
                        print(f"  💾 saved: {p}")
                else:
                    print(f"  ⚠️  output に保存可能な base64 データなし: {list(result.get('output', {}).keys()) if isinstance(result.get('output'), dict) else type(result.get('output')).__name__}")
            completed += 1
        finally:
            release_lock(lock_file)

    print(f"\n結果: 成功 {completed} / 失敗 {failed} / 合計 {len(prompts)}")
    print(f"job_map: {args.output_root}/job_map_{args.endpoint}.json")
    print(f"次に: python3 scripts/serverless_fetch.py --endpoint {args.endpoint} --output-root {args.output_root}")


if __name__ == "__main__":
    main()

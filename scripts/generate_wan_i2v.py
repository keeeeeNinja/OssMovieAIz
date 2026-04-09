#!/usr/bin/env python3
"""
Wan 2.1 I2V Video Generator via ComfyUI on RunPod

Usage:
  # 単体実行
  python3 scripts/generate_wan_i2v.py \
    --host IP --port PORT \
    --prompts scripts/wan_i2v_prompts.json \
    [--scenes C01,C02,C03] [--pod-id POD_ID]

  # 並列実行（全シーンを両方に渡す → ロックで自動分配）
  python3 scripts/generate_wan_i2v.py --host pod1_ip --port pod1_port --prompts ... --pod-id xxx &
  python3 scripts/generate_wan_i2v.py --host pod2_ip --port pod2_port --prompts ... --pod-id yyy --terminate &

  # ロック残骸を掃除してから実行
  python3 scripts/generate_wan_i2v.py --clean-locks --host ...

機能:
  - ロックベース自動分配: 複数プロセスが同じシーンリストを受け取り、ロックで排他制御
  - 2周目リトライ: 1周目で別Podに任せたシーンが未完了なら自動で引き受ける
  - 画像自動アップロード: 参照画像がPodになければ自動でscpアップロード
  - Pod自動停止: --pod-id指定で完了後にPod停止/削除を提案
  - 古いロック自動削除: プロセスが死んだロックファイルは起動時に自動クリーンアップ
"""

import argparse
import fcntl
import json
import os
import random
import subprocess
import sys
import time

SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
RUNPOD_API_URL = "https://api.runpod.io/graphql"
COMFYUI_OUTPUT_DIR = "/workspace/ComfyUI/output"
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../作業中動画")
LOCAL_OUTPUT_DIR = DEFAULT_OUTPUT_DIR  # --output-dir で上書き可能
WORKFLOW_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "../.claude/skills/wan-video/workflow_template.json")

LOCK_DIR = os.path.join(DEFAULT_OUTPUT_DIR, ".locks")  # --output-dir で連動
NEGATIVE_PROMPT = "blurry, distorted, low quality, shaky, deformed hands, extra fingers, watermark, text overlay"


def try_lock(cut_id):
    """シーンのロックを取得する。取れたらTrueとファイルオブジェクト、取れなかったらFalseとNone"""
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
    """ロックを解放する"""
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
    """全ロックファイルを削除する"""
    if os.path.exists(LOCK_DIR):
        for f in os.listdir(LOCK_DIR):
            if f.endswith(".lock"):
                try:
                    os.unlink(os.path.join(LOCK_DIR, f))
                except Exception:
                    pass


def ssh(host, port, cmd, check=True, timeout=30):
    full_cmd = [
        "ssh", "-T", "-o", "StrictHostKeyChecking=no",
        "-o", f"ConnectTimeout={timeout}",
        f"root@{host}", "-p", str(port), "-i", SSH_KEY,
        cmd
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout+10)
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


def _runpod_mutation(mutation_query, pod_id, action_label):
    """RunPod APIにmutationを送信する共通処理"""
    api_key = os.environ.get("RUNPOD_API_KEY", "")
    if not api_key:
        print(f"⚠️  RUNPOD_API_KEY が未設定のためPod{action_label}できません", file=sys.stderr)
        return False
    import urllib.request
    query = json.dumps({"query": mutation_query})
    req = urllib.request.Request(
        RUNPOD_API_URL,
        data=query.encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if "errors" in result:
            print(f"⚠️  Pod{action_label}エラー: {result['errors']}", file=sys.stderr)
            return False
        print(f"✅ Pod {pod_id} を{action_label}しました")
        return True
    except Exception as e:
        print(f"⚠️  Pod{action_label}に失敗: {e}", file=sys.stderr)
        return False


def stop_pod(pod_id):
    """RunPod APIでPodを停止する（Volume付き向け。再開可能）"""
    return _runpod_mutation(
        f'mutation {{ podStop(input: {{ podId: "{pod_id}" }}) {{ id desiredStatus }} }}',
        pod_id, "停止"
    )


def terminate_pod(pod_id):
    """RunPod APIでPodを削除する（Volumeなし向け。完全削除で課金停止）"""
    return _runpod_mutation(
        f'mutation {{ podTerminate(input: {{ podId: "{pod_id}" }}) }}',
        pod_id, "削除"
    )


def scp_upload(host, port, local_path, remote_path):
    """ローカルファイルをリモートにアップロード"""
    cmd = [
        "scp", "-o", "StrictHostKeyChecking=no",
        "-P", str(port), "-i", SSH_KEY,
        local_path, f"root@{host}:{remote_path}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def upload_images(host, port, prompts):
    """プロンプトで参照される画像をPodにアップロード（未アップロードのみ）"""
    remote_input_dir = "/workspace/ComfyUI/input"
    image_names = list({p["image"] for p in prompts})
    # リモートに既にある画像を確認
    existing = ssh(host, port, f"ls {remote_input_dir}/ 2>/dev/null", check=False)
    existing_files = set(existing.split())

    uploaded = 0
    for img in image_names:
        if img in existing_files:
            continue
        local_path = os.path.join(LOCAL_OUTPUT_DIR, img)
        if not os.path.exists(local_path):
            print(f"  ⚠️  ローカルに画像がありません: {local_path}", file=sys.stderr)
            continue
        ok = scp_upload(host, port, local_path, f"{remote_input_dir}/{img}")
        if ok:
            uploaded += 1
        else:
            print(f"  ⚠️  アップロード失敗: {img}", file=sys.stderr)
    return uploaded, len(image_names)


def check_comfyui(host, port):
    out = ssh(host, port,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/",
        check=False)
    return out.strip() == "200"


def build_workflow(template, prompt_text, image_name, output_prefix, seed, width, height):
    """テンプレートのプレースホルダーを置換"""
    wf_str = json.dumps(template)
    coefficients = "i2v_480" if width <= 480 else "i2v_720"
    wf_str = wf_str.replace("[PROMPT]", prompt_text)
    wf_str = wf_str.replace("[NEGATIVE]", NEGATIVE_PROMPT)
    wf_str = wf_str.replace("[IMAGE_NAME]", image_name)
    wf_str = wf_str.replace("[OUTPUT_PREFIX]", output_prefix)
    wf_str = wf_str.replace('"[SEED_VALUE]"', str(seed))
    wf_str = wf_str.replace('"[WIDTH]"', str(width))
    wf_str = wf_str.replace('"[HEIGHT]"', str(height))
    wf_str = wf_str.replace("[COEFFICIENTS]", coefficients)
    return json.loads(wf_str)


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
    out = ssh(host, port, cmd, check=False, timeout=30)
    try:
        resp = json.loads(out)
        if "error" in resp:
            print(f"  API error: {resp['error']}", file=sys.stderr)
            if "node_errors" in resp:
                for node_id, err in resp["node_errors"].items():
                    print(f"    Node {node_id}: {err}", file=sys.stderr)
            return ""
        return resp.get("prompt_id", "")
    except Exception:
        print(f"  Submit error: {out}", file=sys.stderr)
        return ""


def poll_until_done(host, port, prompt_id, timeout=900):
    """生成完了を待つ（Wan I2Vは6分程度かかる）"""
    start = time.time()
    while time.time() - start < timeout:
        out = ssh(host, port,
            f"curl -s http://localhost:8188/history/{prompt_id}",
            check=False, timeout=15)
        try:
            hist = json.loads(out)
            if prompt_id in hist:
                outputs = hist[prompt_id].get("outputs", {})
                if outputs:
                    return outputs
        except Exception:
            pass
        elapsed = int(time.time() - start)
        # VRAM usage check (optional, skip on timeout)
        try:
            vram = ssh(host, port, "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits", check=False, timeout=30)
            print(f"  生成中... ({elapsed}s) VRAM: {vram}MiB", flush=True)
        except Exception:
            print(f"  生成中... ({elapsed}s)", flush=True)
        time.sleep(30)
    return None


def find_output_file(host, port, prefix):
    out = ssh(host, port,
        f"ls -t {COMFYUI_OUTPUT_DIR}/{prefix}*.mp4 2>/dev/null | head -1",
        check=False)
    return out.strip()


def main():
    parser = argparse.ArgumentParser(description="Wan 2.1 I2V Video Generator")
    parser.add_argument("--host", required=True, help="RunPod IP")
    parser.add_argument("--port", required=True, type=int, help="RunPod SSH port")
    parser.add_argument("--prompts", required=True, help="プロンプトJSONファイル")
    parser.add_argument("--scenes", default="", help="生成するシーンをカンマ区切りで指定（例: C01,C02,C03）")
    parser.add_argument("--width", default=480, type=int)
    parser.add_argument("--height", default=832, type=int)
    parser.add_argument("--seed", default=0, type=int, help="シード値（0=ランダム）")
    parser.add_argument("--pod-id", default="", help="RunPod Pod ID（指定すると完了後にPod停止を提案）")
    parser.add_argument("--terminate", action="store_true", help="Pod停止時にterminateを使う（Volumeなし用）")
    parser.add_argument("--clean-locks", action="store_true", help="開始前にロックファイルを全削除する")
    parser.add_argument("--output-dir", default="", help="入出力ディレクトリ（デフォルト: 作業中動画/）")
    args = parser.parse_args()

    # 出力先ディレクトリの上書き
    global LOCAL_OUTPUT_DIR, LOCK_DIR
    if args.output_dir:
        LOCAL_OUTPUT_DIR = args.output_dir
        LOCK_DIR = os.path.join(args.output_dir, ".locks")
        os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    # フィルタ
    scene_filter = set(args.scenes.split(",")) if args.scenes else None

    # 接続確認
    print(f"RunPodに接続中: {args.host}:{args.port}")
    if not check_comfyui(args.host, args.port):
        print("ComfyUIが起動していません", file=sys.stderr)
        sys.exit(1)
    print("ComfyUI: OK")

    # ワークフローテンプレート読み込み
    with open(WORKFLOW_TEMPLATE) as f:
        template = json.load(f)
    print(f"ワークフローテンプレート: {WORKFLOW_TEMPLATE}")

    # プロンプト読み込み
    with open(args.prompts) as f:
        prompts = json.load(f)

    if scene_filter:
        prompts = [p for p in prompts if p["id"] in scene_filter]
        print(f"対象シーン: {[p['id'] for p in prompts]}")

    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)

    # ロックファイルのクリーンアップ
    if args.clean_locks:
        cleanup_locks()
        print("ロックファイルを削除しました")

    # 古いロックの自動クリーンアップ（60秒以上前のロックは削除）
    if os.path.exists(LOCK_DIR):
        now = time.time()
        for lf in os.listdir(LOCK_DIR):
            if lf.endswith(".lock"):
                lp = os.path.join(LOCK_DIR, lf)
                try:
                    if now - os.path.getmtime(lp) > 60:
                        # ロックが取れるか試す（プロセスが死んでいればロック取得可能）
                        try:
                            f = open(lp, "r+")
                            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            # ロック取れた = 前のプロセスは死んでいる → 削除
                            fcntl.flock(f, fcntl.LOCK_UN)
                            f.close()
                            os.unlink(lp)
                            print(f"  古いロックを削除: {lf}")
                        except (OSError, IOError):
                            pass  # ロック取れない = まだ生成中のプロセスがいる
                except Exception:
                    pass

    # 参照画像のアップロード
    print("参照画像を確認中...")
    uploaded, total = upload_images(args.host, args.port, prompts)
    if uploaded > 0:
        print(f"  {uploaded}/{total} 枚アップロード完了")
    else:
        print(f"  全 {total} 枚アップロード済み")

    # 生成ループ（ロックベースの分散処理、最大2周）
    results = []

    def run_generation_pass(prompts_list, pass_num):
        """1周分の生成処理。結果リストを返す"""
        pass_results = []
        lock_files = {}
        try:
            for i, item in enumerate(prompts_list, 1):
                cut_id = item["id"]
                prompt_text = item["prompt"]
                image_name = item["image"]
                output_prefix = f"scene_{cut_id}_wan21"
                local_file = os.path.join(LOCAL_OUTPUT_DIR, f"scene_{cut_id}_wan21.mp4")

                # 既に完成済み
                if os.path.exists(local_file):
                    if pass_num == 1:
                        print(f"\n[{cut_id}] スキップ（既存ファイルあり）")
                    pass_results.append({"id": cut_id, "file": local_file, "status": "skipped"})
                    continue

                # ロック取得を試みる
                locked, lock_file = try_lock(cut_id)
                if not locked:
                    if pass_num == 1:
                        print(f"\n[{cut_id}] スキップ（別Podが生成中）")
                    pass_results.append({"id": cut_id, "status": "skipped_by_other"})
                    continue

                lock_files[cut_id] = lock_file

                # ロック取得後に再度ファイル存在チェック
                if os.path.exists(local_file):
                    print(f"\n[{cut_id}] スキップ（別Podが完了済み）")
                    pass_results.append({"id": cut_id, "file": local_file, "status": "skipped"})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                label = f"({pass_num}周目)" if pass_num > 1 else ""
                print(f"\n[{cut_id}] 生成開始 {label}({i}/{len(prompts_list)})")
                print(f"  画像: {image_name}")
                print(f"  プロンプト: {prompt_text[:80]}...")

                seed = args.seed if args.seed > 0 else random.randint(1, 2**32)
                wf = build_workflow(template, prompt_text, image_name, output_prefix, seed,
                                   args.width, args.height)

                prompt_id = submit_workflow(args.host, args.port, wf)
                if not prompt_id:
                    print(f"  [エラー] ワークフロー投入失敗", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "error", "seed": seed})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                print(f"  prompt_id: {prompt_id}")
                print(f"  seed: {seed}")
                outputs = poll_until_done(args.host, args.port, prompt_id)

                if not outputs:
                    print(f"  [エラー] タイムアウト（15分）", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "timeout", "seed": seed})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                remote_file = find_output_file(args.host, args.port, output_prefix)
                if not remote_file:
                    print(f"  [エラー] 出力ファイルが見つかりません", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "error", "seed": seed})
                    release_lock(cut_id, lock_file)
                    del lock_files[cut_id]
                    continue

                ok = scp_download(args.host, args.port, remote_file, local_file)
                if ok:
                    print(f"  ダウンロード完了: {local_file}")
                    pass_results.append({"id": cut_id, "file": local_file, "status": "ok", "seed": seed})
                else:
                    print(f"  [エラー] ダウンロード失敗", file=sys.stderr)
                    pass_results.append({"id": cut_id, "status": "error", "seed": seed})

                release_lock(cut_id, lock_file)
                del lock_files[cut_id]

        finally:
            for cid, lf in lock_files.items():
                release_lock(cid, lf)

        return pass_results

    # --- 1周目 ---
    results = run_generation_pass(prompts, 1)

    # --- 2周目: 別Podに任せたが未完了のシーンを拾う ---
    skipped_other_ids = {r["id"] for r in results if r["status"] == "skipped_by_other"}
    if skipped_other_ids:
        # 少し待って別Podの完了を待つ
        time.sleep(10)
        # まだファイルが無いシーンだけ2周目の対象にする
        retry_prompts = []
        for item in prompts:
            if item["id"] in skipped_other_ids:
                local_file = os.path.join(LOCAL_OUTPUT_DIR, f"scene_{item['id']}_wan21.mp4")
                if not os.path.exists(local_file):
                    retry_prompts.append(item)
        if retry_prompts:
            print(f"\n--- 2周目: 未完了 {len(retry_prompts)} シーンをリトライ ---")
            retry_results = run_generation_pass(retry_prompts, 2)
            # 2周目の結果で skipped_by_other を上書き
            retry_map = {r["id"]: r for r in retry_results}
            results = [retry_map.get(r["id"], r) if r["status"] == "skipped_by_other" else r for r in results]

    # 結果サマリー
    print("\n" + "=" * 50)
    print("Wan 2.1 I2V 生成完了サマリー")
    print("=" * 50)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skip_count = sum(1 for r in results if r["status"] in ("skipped", "skipped_by_other"))
    other_count = sum(1 for r in results if r["status"] == "skipped_by_other")
    err_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    print(f"成功: {ok_count}  スキップ: {skip_count}（うち別Pod: {other_count}）  エラー: {err_count}")
    for r in results:
        icon = {"ok": "OK", "skipped": "SKIP", "skipped_by_other": "OTHER", "error": "ERR", "timeout": "TIMEOUT"}.get(r["status"], "?")
        seed_str = f" (seed: {r['seed']})" if "seed" in r else ""
        print(f"  [{icon}] {r['id']}: {r.get('file', r['status'])}{seed_str}")

    # Pod停止の提案
    if args.pod_id:
        action = "削除" if args.terminate else "停止"
        if err_count > 0:
            print(f"\n⚠️  エラーが {err_count} 件あります。Pod {args.pod_id} はまだ{action}しません。")
            print("  ComfyUI再起動後にリトライできます。")
        else:
            print(f"\n全シーン完了。Pod {args.pod_id} を{action}しますか？ [y/N] ", end="", flush=True)
            try:
                answer = input().strip().lower()
                if answer in ("y", "yes"):
                    if args.terminate:
                        terminate_pod(args.pod_id)
                    else:
                        stop_pod(args.pod_id)
                else:
                    print("Podは起動したままです。不要になったら手動で停止してください。")
            except (EOFError, KeyboardInterrupt):
                print("\nPodは起動したままです。")


if __name__ == "__main__":
    main()

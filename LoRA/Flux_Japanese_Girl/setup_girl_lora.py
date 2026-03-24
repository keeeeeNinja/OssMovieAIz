#!/usr/bin/env python3
"""
Flux Japanese Girl LoRA - 完全セットアップ & 学習スクリプト
============================================================
使い方:
  1. echo 'hf_xxxxxx' > /tmp/hf_token.txt
  2. python3 /workspace/setup_girl_lora.py

このスクリプトが自動でやること:
  - HFトークン確認
  - FLUX.1-devモデル確認
  - データセット確認
  - ai-toolkit インストール（/root/ ローカルに）
  - save_training_config の quota エラー対策パッチ
  - 学習設定ファイル生成
  - バックグラウンドで学習開始
"""

import os
import sys
import subprocess
import shutil

LOG_FILE = "/tmp/lora_train.log"
AITOOLKIT_DIR = "/root/ai-toolkit"
FLUX_PATH = "/workspace/models/flux_dev"
DATASET_DIR = "/workspace/datasets/Flux_Japanese_Girl"
OUTPUT_DIR = "/workspace/output/flux_japanese_girl_lora"
CONFIG_PATH = "/tmp/flux_girl_lora.yaml"


def banner(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run(cmd, check=True):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(result.stderr.strip())
    return result


# ==============================================================
# Step 1: HF Token
# ==============================================================
banner("Step 1: HF Token チェック")

if not os.path.exists("/tmp/hf_token.txt"):
    print("ERROR: /tmp/hf_token.txt が見つかりません")
    print("実行してください: echo 'hf_xxxxx' > /tmp/hf_token.txt")
    sys.exit(1)

with open("/tmp/hf_token.txt") as f:
    hf_token = f.read().strip()

if not hf_token or len(hf_token) < 10:
    print("ERROR: HF token が空または短すぎます")
    sys.exit(1)

os.environ["HF_TOKEN"] = hf_token
print(f"  OK: HF_TOKEN = {hf_token[:10]}... ({len(hf_token)} chars)")


# ==============================================================
# Step 2: FLUX.1-dev モデル確認
# ==============================================================
banner("Step 2: FLUX.1-dev モデル確認")

required = ["ae.safetensors", "transformer", "text_encoder", "text_encoder_2", "vae"]
all_ok = True
for item in required:
    path = os.path.join(FLUX_PATH, item)
    exists = os.path.exists(path)
    status = "OK" if exists else "MISSING"
    print(f"  [{status}] {item}")
    if not exists:
        all_ok = False

if not all_ok:
    print("ERROR: FLUX.1-dev が不完全です")
    sys.exit(1)

print("  OK: FLUX.1-dev 確認完了")


# ==============================================================
# Step 3: データセット確認
# ==============================================================
banner("Step 3: データセット確認")

if not os.path.exists(DATASET_DIR):
    print(f"ERROR: {DATASET_DIR} が見つかりません")
    sys.exit(1)

files = os.listdir(DATASET_DIR)
images = [f for f in files if f.endswith(".png") or f.endswith(".jpg")]
captions = [f for f in files if f.endswith(".txt")]

print(f"  画像:      {len(images)} 枚")
print(f"  キャプション: {len(captions)} 個")

if len(images) < 15:
    print("ERROR: 画像が少なすぎます（15枚以上必要）")
    sys.exit(1)

missing_captions = []
for img in images:
    base = os.path.splitext(img)[0]
    if f"{base}.txt" not in captions:
        missing_captions.append(img)

if missing_captions:
    print(f"  WARNING: キャプションなし: {missing_captions}")
else:
    print("  OK: 全画像にキャプションあり")


# ==============================================================
# Step 4: Python パッケージ確認 & インストール
# ==============================================================
banner("Step 4: Python パッケージ確認")

def check_and_install(package, import_name=None):
    if import_name is None:
        import_name = package.replace("-", "_").split("[")[0]
    try:
        __import__(import_name)
        print(f"  OK: {package}")
        return True
    except ImportError:
        print(f"  Installing: {package}")
        run(f"pip install {package} -q")
        return False

check_and_install("bitsandbytes")
check_and_install("diffusers")
check_and_install("transformers")
check_and_install("accelerate")
check_and_install("peft")
check_and_install("sentencepiece")
check_and_install("ftfy")


# ==============================================================
# Step 5: ai-toolkit インストール（ローカルストレージ /root/ に）
# ==============================================================
banner("Step 5: ai-toolkit セットアップ（/root/ ローカルストレージ）")

if not os.path.exists(AITOOLKIT_DIR):
    print("  ai-toolkit を /root/ にインストール中...")
    run(f"git clone https://github.com/ostris/ai-toolkit.git {AITOOLKIT_DIR}")
    run(f"pip install -r {AITOOLKIT_DIR}/requirements.txt -q")
    print("  OK: ai-toolkit インストール完了")
else:
    print(f"  OK: 既にインストール済み → {AITOOLKIT_DIR}")
    # requirements の確認だけ実施
    run(f"pip install -r {AITOOLKIT_DIR}/requirements.txt -q --no-deps", check=False)


# ==============================================================
# Step 6: save_training_config quota エラー対策パッチ
# ==============================================================
banner("Step 6: ai-toolkit パッチ適用（quota エラー対策）")

patch_target = os.path.join(AITOOLKIT_DIR, "jobs/process/BaseTrainProcess.py")

with open(patch_target, "r") as f:
    content = f.read()

OLD_CODE = """    def save_training_config(self):
        os.makedirs(self.save_root, exist_ok=True)
        save_dif = os.path.join(self.save_root, f'config.yaml')
        with open(save_dif, 'w') as f:
            yaml.dump(self.job.raw_config, f)"""

NEW_CODE = """    def save_training_config(self):
        try:
            os.makedirs(self.save_root, exist_ok=True)
            save_dif = os.path.join(self.save_root, f'config.yaml')
            with open(save_dif, 'w') as f:
                yaml.dump(self.job.raw_config, f)
        except OSError as e:
            print(f"  [Warning] save_training_config skipped: {e}")"""

if OLD_CODE in content:
    content = content.replace(OLD_CODE, NEW_CODE)
    with open(patch_target, "w") as f:
        f.write(content)
    print("  OK: パッチ適用完了")
elif "save_training_config skipped" in content:
    print("  OK: 既にパッチ済み")
else:
    print("  WARNING: パッチ対象コードが見つかりません（バージョン違いの可能性）")
    print("  学習は続行します（エラーが出た場合は手動対応が必要）")


# ==============================================================
# Step 7: 学習設定ファイル生成（Python yaml で文字化け回避）
# ==============================================================
banner("Step 7: 学習設定ファイル生成")

import yaml

config = {
    "job": "extension",
    "config": {
        "name": "flux_japanese_girl_v1",
        "process": [{
            "type": "sd_trainer",
            "training_folder": OUTPUT_DIR,
            "device": "cuda:0",
            "trigger_word": "ohwx woman",
            "network": {
                "type": "lora",
                "linear": 16,
                "linear_alpha": 16
            },
            "save": {
                "dtype": "float16",
                "save_every": 500,
                "max_step_saves_to_keep": 4
            },
            "datasets": [{
                "folder_path": DATASET_DIR,
                "image_size": [512, 512],
                "caption_ext": "txt",
                "caption_dropout_rate": 0.05,
                "shuffle_tokens": False,
                "cache_latents_to_disk": False,  # NFS書き込みを最小化するためOFF
                "is_regularization": False
            }],
            "train": {
                "batch_size": 1,
                "steps": 2000,
                "gradient_accumulation_steps": 1,
                "train_unet": True,
                "train_text_encoder": False,
                "gradient_checkpointing": True,
                "noise_scheduler": "flowmatch",
                "optimizer": "adamw8bit",
                "lr": 1e-4,
                "lr_scheduler": "constant",
                "max_grad_norm": 1.0,
                "dtype": "bf16",
                "ema_config": {
                    "use_ema": True,
                    "ema_decay": 0.99
                }
            },
            "model": {
                "name_or_path": FLUX_PATH,
                "is_flux": True,
                "quantize": True
            },
            "sample": {
                "sampler": "flowmatch",
                "sample_every": 500,
                "width": 512,
                "height": 512,
                "prompts": [
                    "ohwx woman, portrait photo, white background, looking at camera",
                    "ohwx woman, full body, standing, white background",
                    "ohwx woman, smiling, upper body, natural light"
                ],
                "neg": "",
                "seed": 42,
                "walk_seed": True,
                "guidance_scale": 4,
                "sample_steps": 20
            }
        }]
    },
    "meta": {
        "name": "[name]",
        "version": "1.0"
    }
}

with open(CONFIG_PATH, "w") as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
print(f"  OK: 設定ファイル → {CONFIG_PATH}")

# 検証
with open(CONFIG_PATH) as f:
    loaded = yaml.safe_load(f)
assert loaded["job"] == "extension", "YAML 検証失敗"
print("  OK: YAML 検証完了")


# ==============================================================
# Step 8: 出力ディレクトリ作成
# ==============================================================
banner("Step 8: 出力ディレクトリ作成")

os.makedirs(OUTPUT_DIR, exist_ok=True)
# 書き込みテスト
test_path = os.path.join(OUTPUT_DIR, ".write_test")
with open(test_path, "w") as f:
    f.write("test")
os.remove(test_path)
print(f"  OK: {OUTPUT_DIR} （書き込みテスト成功）")


# ==============================================================
# Step 9: ComfyUI プロセス停止（VRAM確保）
# ==============================================================
banner("Step 9: VRAM確保（ComfyUI停止）")

result = run("pgrep -f 'comfy' 2>/dev/null", check=False)
if result.returncode == 0 and result.stdout.strip():
    run("pkill -f 'comfy' 2>/dev/null", check=False)
    print("  OK: ComfyUI を停止しました")
else:
    print("  OK: ComfyUIは起動していません")


# ==============================================================
# Step 10: バックグラウンドで学習開始
# ==============================================================
banner("Step 10: LoRA 学習開始")

import subprocess

cmd = f"cd {AITOOLKIT_DIR} && python3 run.py {CONFIG_PATH}"
proc = subprocess.Popen(
    f"nohup bash -c '{cmd}' > {LOG_FILE} 2>&1 &",
    shell=True
)

import time
time.sleep(5)

# プロセス確認
result = run("pgrep -f 'run.py' 2>/dev/null", check=False)
if result.returncode == 0:
    pid = result.stdout.strip()
    print(f"  OK: 学習プロセス起動中 (PID: {pid})")
else:
    print("  WARNING: プロセスが確認できません。ログを確認してください")

print(f"""
{'='*60}
  セットアップ完了！

  学習監視コマンド:
    tail -f {LOG_FILE}

  進捗確認:
    grep -E 'loss|step' {LOG_FILE} | tail -20

  完了確認:
    ls {OUTPUT_DIR}/flux_japanese_girl_v1/
{'='*60}
""")

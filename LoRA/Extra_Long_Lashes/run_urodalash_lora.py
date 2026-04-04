#!/usr/bin/env python3
"""
URDP001 Product LoRA - ai-toolkit (Flux.1-dev) v2
====================================================
修正点（v2）:
  - トリガーワード: UrodaLash_v1 → URDP001
  - 学習画像: 23枚（ワンド露出4枚を除外）
  - 正則化画像: 使用しない
  - LR: 1e-4 → 2e-4
  - ステップ: 2000 → 3000
  - 解像度: 1024x1024を確実に強制
  - サンプルプロンプト: lash/eye関連ワードを全削除

データセット構成:
  学習画像  23枚: /root/datasets/UrodaLash/images/
  正則化画像: なし（今回は使用しない）

実行前の準備:
  echo 'hf_xxxxx' > /tmp/hf_token.txt
  python3 /workspace/run_urodalash_lora.py
"""

import os, sys, subprocess, time, yaml

HF_TOKEN = open("/tmp/hf_token.txt").read().strip()
os.environ["HF_TOKEN"] = HF_TOKEN

DATASET_DIR   = "/root/datasets/UrodaLash/images"
AITOOLKIT_DIR = "/workspace/ai-toolkit"
OUTPUT_DIR    = "/workspace/output/URDP001_v2"
CONFIG_PATH   = "/tmp/urdp001_lora.yaml"
LOG_TRAIN     = "/workspace/urdp001_train.log"

def banner(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")

def run(cmd, check=True, **kwargs):
    print(f"  $ {cmd[:120]}")
    result = subprocess.run(cmd, shell=True, **kwargs)
    if check and result.returncode != 0:
        print(f"  ERROR: exit code {result.returncode}")
        sys.exit(1)
    return result

# =====================================================
# Step 1: データセット確認
# =====================================================
banner("Step 1: データセット確認")

imgs = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith(".png")]) if os.path.exists(DATASET_DIR) else []
txts = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]) if os.path.exists(DATASET_DIR) else []

print(f"  学習画像    : {len(imgs)}枚")
print(f"  キャプション: {len(txts)}個")

if len(imgs) < 10:
    print(f"\n  ERROR: 学習画像が不足しています ({len(imgs)}枚)")
    sys.exit(1)

if len(imgs) != len(txts):
    missing = set(f.replace(".png", "") for f in imgs) - set(f.replace(".txt", "") for f in txts)
    print(f"  WARNING: キャプションが不足: {missing}")
    sys.exit(1)

# キャプションにURDP001が含まれているか確認
missing_trigger = []
for txt in txts:
    content = open(os.path.join(DATASET_DIR, txt)).read()
    if "URDP001" not in content:
        missing_trigger.append(txt)
if missing_trigger:
    print(f"  ERROR: URDP001が含まれていないキャプション: {missing_trigger}")
    sys.exit(1)

print("  OK: 全キャプションにURDP001あり")

# =====================================================
# Step 2: ai-toolkit セットアップ
# =====================================================
banner("Step 2: ai-toolkit セットアップ")

if not os.path.exists(AITOOLKIT_DIR):
    print("  インストール中...")
    run(f"git clone https://github.com/ostris/ai-toolkit.git {AITOOLKIT_DIR}")
    run(f"pip install -r {AITOOLKIT_DIR}/requirements.txt -q")
    print("  OK: インストール完了")
else:
    print(f"  OK: 既存 → {AITOOLKIT_DIR}")

# =====================================================
# Step 3: ai-toolkit パッチ（save_training_config OSエラー回避）
# =====================================================
banner("Step 3: ai-toolkit パッチ")

patch_file = f"{AITOOLKIT_DIR}/jobs/process/BaseTrainProcess.py"
if os.path.exists(patch_file):
    content = open(patch_file).read()
    OLD = """    def save_training_config(self):
        os.makedirs(self.save_root, exist_ok=True)
        save_dif = os.path.join(self.save_root, f'config.yaml')
        with open(save_dif, 'w') as f:
            yaml.dump(self.job.raw_config, f)"""
    NEW = """    def save_training_config(self):
        try:
            os.makedirs(self.save_root, exist_ok=True)
            save_dif = os.path.join(self.save_root, f'config.yaml')
            with open(save_dif, 'w') as f:
                yaml.dump(self.job.raw_config, f)
        except OSError as e:
            print(f"  [Warning] save_training_config skipped: {e}")"""
    if OLD in content:
        open(patch_file, "w").write(content.replace(OLD, NEW))
        print("  OK: パッチ適用")
    elif "save_training_config skipped" in content:
        print("  OK: 既にパッチ済み")
    else:
        print("  WARNING: パッチ対象なし（バージョン違い）")
else:
    print("  SKIP: パッチ対象ファイルなし")

# =====================================================
# Step 4: 学習設定ファイル生成
# =====================================================
banner("Step 4: 学習設定ファイル生成")

config = {
    "job": "extension",
    "config": {
        "name": "URDP001_v2",
        "process": [{
            "type": "sd_trainer",
            "training_folder": OUTPUT_DIR,
            "device": "cuda:0",
            "trigger_word": "URDP001",
            "network": {
                "type": "lora",
                "linear": 16,
                "linear_alpha": 16,
            },
            "save": {
                "dtype": "float16",
                "save_every": 500,
                "max_step_saves_to_keep": 6,
            },
            "datasets": [{
                "folder_path": DATASET_DIR,
                "image_size": [1024, 1024],
                "caption_ext": "txt",
                "caption_dropout_rate": 0.05,
                "shuffle_tokens": False,
                "cache_latents_to_disk": False,
                "is_regularization": False,
                "resolution": [1024],
                "min_bucket_resolution": 1024,
                "max_bucket_resolution": 1024,
            }],
            "train": {
                "batch_size": 1,
                "steps": 3000,
                "gradient_accumulation_steps": 1,
                "train_unet": True,
                "train_text_encoder": False,
                "gradient_checkpointing": True,
                "noise_scheduler": "flowmatch",
                "optimizer": "adamw8bit",
                "lr": 2e-4,
                "lr_scheduler": "cosine",
                "lr_warmup_steps": 200,
                "max_grad_norm": 1.0,
                "dtype": "bf16",
                "ema_config": {"use_ema": True, "ema_decay": 0.99},
            },
            "model": {
                "name_or_path": "black-forest-labs/FLUX.1-dev",
                "is_flux": True,
                "quantize": True,
            },
            "sample": {
                "sampler": "flowmatch",
                "sample_every": 500,
                "width": 1024,
                "height": 1024,
                "prompts": [
                    "URDP001, product on white background, studio lighting, centered composition",
                    "URDP001, held in a hand, light gray background, natural indoor lighting",
                    "URDP001, standing upright on a surface, neutral background, soft lighting",
                    "URDP001, lying on its side, horizontal orientation, neutral background, soft lighting",
                ],
                "neg": "",
                "seed": 42,
                "walk_seed": True,
                "guidance_scale": 4,
                "sample_steps": 20,
            },
        }]
    },
    "meta": {"name": "[name]", "version": "1.0"},
}

with open(CONFIG_PATH, "w") as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

print(f"  OK: {CONFIG_PATH}")
print(f"""
  設定サマリー:
    トリガーワード : URDP001
    学習画像       : {len(imgs)}枚
    正則化画像     : なし
    ステップ数     : 3000 (保存: 500ごと)
    network_dim    : 16 / alpha: 16
    learning_rate  : 2e-4 (cosine, warmup 200steps)
    解像度         : 1024x1024（固定）
    出力先         : {OUTPUT_DIR}
""")

# =====================================================
# Step 5: 出力ディレクトリ 書き込みテスト
# =====================================================
banner("Step 5: Network Volume 書き込みテスト")
os.makedirs(OUTPUT_DIR, exist_ok=True)
test = os.path.join(OUTPUT_DIR, ".write_test")
with open(test, "wb") as f:
    f.write(b"0" * 1024 * 1024 * 200)
os.remove(test)
print(f"  OK: 200MB 書き込みテスト成功 → {OUTPUT_DIR}")

# =====================================================
# Step 6: ComfyUI 停止（VRAM確保）
# =====================================================
banner("Step 6: VRAM確保")
run("pkill -f 'comfy' 2>/dev/null", check=False, capture_output=True)
run("pkill -f 'main.py' 2>/dev/null", check=False, capture_output=True)
time.sleep(3)
print("  OK: ComfyUI停止")

# =====================================================
# Step 7: 学習開始
# =====================================================
banner("Step 7: LoRA学習開始")
print(f"  ログ: {LOG_TRAIN}")

os.chdir(AITOOLKIT_DIR)
os.execv(sys.executable, [sys.executable, "run.py", CONFIG_PATH])

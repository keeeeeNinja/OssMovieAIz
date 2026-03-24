#!/usr/bin/env python3
"""
Flux Japanese Girl LoRA - 完全自動実行スクリプト
===================================================
全てをローカルストレージ(/root/)で動かす方針:
  - データセット: /root/datasets/FluxGirlLoRA/ (既に配置済み)
  - FLUXモデル: HFキャッシュ自動DL (~/.cache/huggingface/)
  - JoyCaptionモデル: HFキャッシュ自動DL
  - 出力LoRA: /workspace/output/ (小ファイルなのでOK)

実行前に: echo 'hf_xxxxx' > /tmp/hf_token.txt
"""

import os, sys, subprocess, time

HF_TOKEN = open("/tmp/hf_token.txt").read().strip()
os.environ["HF_TOKEN"] = HF_TOKEN

DATASET_DIR = "/root/datasets/FluxGirlLoRA"
AITOOLKIT_DIR = "/root/ai-toolkit"
OUTPUT_DIR = "/workspace/output/flux_japanese_girl_lora"
CONFIG_PATH = "/tmp/flux_girl_lora.yaml"
LOG_TRAIN = "/tmp/lora_train.log"
LOG_JOY = "/tmp/joycaption_girl.log"

def banner(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")

def run(cmd, **kwargs):
    print(f"  $ {cmd[:100]}")
    return subprocess.run(cmd, shell=True, **kwargs)

# =====================================================
# Step 1: データセット確認
# =====================================================
banner("Step 1: データセット確認")
pngs = [f for f in os.listdir(DATASET_DIR) if f.endswith(".png")]
txts = [f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]
print(f"  画像: {len(pngs)}枚 / キャプション: {len(txts)}個")
if len(pngs) < 15:
    print("ERROR: 画像が不足しています")
    sys.exit(1)

# =====================================================
# Step 2: JoyCaption でキャプション生成（未生成のみ）
# =====================================================
needs_caption = [
    f for f in pngs
    if not os.path.exists(os.path.join(DATASET_DIR, f.replace(".png", ".txt")))
]

if needs_caption:
    banner(f"Step 2: JoyCaption キャプション生成 ({len(needs_caption)}枚)")
    import torch
    from pathlib import Path
    from PIL import Image
    from transformers import AutoProcessor, LlavaForConditionalGeneration

    MODEL_ID = "fancyfeast/llama-joycaption-alpha-two-hf-llava"
    TRIGGER = "ohwx woman"
    PROMPT = (
        f"Write a detailed caption for this image. "
        f"Start the caption with '{TRIGGER}'. "
        f"Describe the person's appearance, clothing, pose, expression, and background."
    )

    print("  モデルロード中...")
    processor = AutoProcessor.from_pretrained(MODEL_ID, token=HF_TOKEN, use_fast=False)
    model = LlavaForConditionalGeneration.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto", token=HF_TOKEN
    )
    model.eval()
    print("  OK: モデルロード完了")

    for fname in sorted(needs_caption):
        img_path = os.path.join(DATASET_DIR, fname)
        txt_path = img_path.replace(".png", ".txt")
        image = Image.open(img_path).convert("RGB")
        messages = [{"role": "user", "content": f"<image>\n{PROMPT}"}]
        prompt_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(images=image, text=prompt_text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        caption = processor.decode(
            output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()
        if not caption.lower().startswith(TRIGGER.lower()):
            caption = f"{TRIGGER}, {caption}"
        Path(txt_path).write_text(caption)
        print(f"  [{fname}] {caption[:70]}...")

    del model, processor
    import gc; gc.collect()
    import torch; torch.cuda.empty_cache()
    print("  OK: キャプション生成完了")
else:
    banner("Step 2: JoyCaption スキップ（全キャプション生成済み）")
    print(f"  {len(txts)}枚のキャプションが既にあります")

# =====================================================
# Step 3: ai-toolkit セットアップ (ローカル /root/)
# =====================================================
banner("Step 3: ai-toolkit セットアップ")
if not os.path.exists(AITOOLKIT_DIR):
    print("  インストール中...")
    run(f"git clone https://github.com/ostris/ai-toolkit.git {AITOOLKIT_DIR}")
    run(f"pip install -r {AITOOLKIT_DIR}/requirements.txt -q")
    print("  OK: インストール完了")
else:
    print(f"  OK: 既存 → {AITOOLKIT_DIR}")

# =====================================================
# Step 4: save_training_config パッチ
# =====================================================
banner("Step 4: ai-toolkit パッチ")
patch_file = f"{AITOOLKIT_DIR}/jobs/process/BaseTrainProcess.py"
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

# =====================================================
# Step 5: 学習設定ファイル生成
# =====================================================
banner("Step 5: 学習設定ファイル生成")
import yaml

config = {
    "job": "extension",
    "config": {
        "name": "flux_japanese_girl_v2",
        "process": [{
            "type": "sd_trainer",
            "training_folder": OUTPUT_DIR,
            "device": "cuda:0",
            "trigger_word": "ohwx woman",
            "network": {"type": "lora", "linear": 32, "linear_alpha": 32},
            "save": {"dtype": "float16", "save_every": 500, "max_step_saves_to_keep": 5},
            "datasets": [{
                "folder_path": DATASET_DIR,
                "image_size": [512, 512],
                "caption_ext": "txt",
                "caption_dropout_rate": 0.05,
                "shuffle_tokens": False,
                "cache_latents_to_disk": False,
                "is_regularization": False,
            }],
            "train": {
                "batch_size": 1,
                "steps": 2500,
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
                "width": 512,
                "height": 512,
                "prompts": [
                    "ohwx woman, portrait photo, white background, looking at camera",
                    "ohwx woman, full body, standing, white background",
                    "ohwx woman, smiling, upper body, natural light",
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

# 検証
loaded = yaml.safe_load(open(CONFIG_PATH))
assert loaded["job"] == "extension"
print(f"  OK: {CONFIG_PATH}")

# =====================================================
# Step 6: 出力ディレクトリ確認
# =====================================================
banner("Step 6: 出力ディレクトリ確認")
os.makedirs(OUTPUT_DIR, exist_ok=True)
test = os.path.join(OUTPUT_DIR, ".test")
open(test, "w").write("test"); os.remove(test)
print(f"  OK: {OUTPUT_DIR}")

# =====================================================
# Step 7: ComfyUI 停止（VRAM確保）
# =====================================================
banner("Step 7: VRAM確保")
run("pkill -f 'comfy' 2>/dev/null", capture_output=True)
time.sleep(2)
print("  OK: ComfyUI停止（またはもともと未起動）")

# =====================================================
# Step 8: 学習開始
# =====================================================
banner("Step 8: LoRA学習開始")
txts_final = [f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]
pngs_final = [f for f in os.listdir(DATASET_DIR) if f.endswith(".png")]
print(f"  データセット: {len(pngs_final)}枚 / {len(txts_final)}キャプション")
print(f"  設定: 2000steps / LR=1e-4 / LoRA rank=16 / ohwx woman")
print(f"  FLUXはHFから自動DL（初回のみ、~34GB、30-60分）")
print(f"  ログ: {LOG_TRAIN}")

os.chdir(AITOOLKIT_DIR)
os.execv(sys.executable, [sys.executable, "run.py", CONFIG_PATH])

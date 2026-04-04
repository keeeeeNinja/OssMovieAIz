#!/usr/bin/env python3
"""
URDP001 Product LoRA - kohya_ss (Flux.1-dev)
=============================================
設定:
  トリガーワード : URDP001
  学習画像       : 23枚 /root/datasets/UrodaLash/images/
  正則化画像     : 35枚 /root/datasets/UrodaLash/reg_images/
  ツール         : kohya_ss (sd-scripts) flux_train_network.py
  LR             : 1e-4 (cosine_with_restarts, warmup 50steps)
  ステップ       : 2000 (200ごとにサンプル保存)
  network_dim    : 16 / alpha: 8
  loraplus_ratio : 16
  解像度         : 1024x1024

実行前:
  echo 'hf_xxxxx' > /tmp/hf_token.txt
  python3 /workspace/run_urdp001_lora.py
"""

import os, sys, subprocess, time

HF_TOKEN = open("/tmp/hf_token.txt").read().strip()
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

DATASET_DIR   = "/root/datasets/UrodaLash/images"
REG_DIR       = "/root/datasets/UrodaLash/reg_images"
KOHYA_DIR     = "/workspace/kohya_ss"
OUTPUT_DIR    = "/workspace/output/URDP001_v2"
DATASET_TOML  = "/tmp/urdp001_dataset.toml"
MODEL_DIR     = "/workspace/models/flux"
LOG_FILE      = "/workspace/urdp001_train.log"

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

imgs = sorted([f for f in os.listdir(DATASET_DIR) if f.lower().endswith((".png",".jpg"))]) if os.path.exists(DATASET_DIR) else []
txts = sorted([f for f in os.listdir(DATASET_DIR) if f.endswith(".txt")]) if os.path.exists(DATASET_DIR) else []
regs = sorted([f for f in os.listdir(REG_DIR) if f.lower().endswith((".png",".jpg"))]) if os.path.exists(REG_DIR) else []

print(f"  学習画像    : {len(imgs)}枚")
print(f"  キャプション: {len(txts)}個")
print(f"  正則化画像  : {len(regs)}枚")

if len(imgs) < 10:
    print(f"  ERROR: 学習画像不足 ({len(imgs)}枚)")
    sys.exit(1)
if len(imgs) != len(txts):
    print(f"  ERROR: 画像とキャプション数が一致しない")
    sys.exit(1)

# URDP001がキャプションに含まれているか確認
for txt in txts:
    content = open(os.path.join(DATASET_DIR, txt)).read()
    if "URDP001" not in content:
        print(f"  ERROR: URDP001が含まれていない: {txt}")
        sys.exit(1)

print("  OK")

# =====================================================
# Step 2: Fluxモデルのダウンロード
# =====================================================
banner("Step 2: Fluxモデル確認・ダウンロード")

os.makedirs(MODEL_DIR, exist_ok=True)

flux_model  = f"{MODEL_DIR}/flux1-dev.safetensors"
clip_l      = f"{MODEL_DIR}/clip_l.safetensors"
t5xxl       = f"{MODEL_DIR}/t5xxl_fp16.safetensors"
ae          = f"{MODEL_DIR}/ae.safetensors"

if not os.path.exists(flux_model):
    print("  Flux1-dev ダウンロード中... (約24GB、時間がかかります)")
    run(f"huggingface-cli download black-forest-labs/FLUX.1-dev flux1-dev.safetensors --local-dir {MODEL_DIR} --token {HF_TOKEN}")
else:
    print(f"  OK: flux1-dev.safetensors")

if not os.path.exists(clip_l):
    print("  clip_l ダウンロード中...")
    run(f"huggingface-cli download comfyanonymous/flux_text_encoders clip_l.safetensors --local-dir {MODEL_DIR}")
else:
    print(f"  OK: clip_l.safetensors")

if not os.path.exists(t5xxl):
    print("  t5xxl ダウンロード中...")
    run(f"huggingface-cli download comfyanonymous/flux_text_encoders t5xxl_fp16.safetensors --local-dir {MODEL_DIR}")
else:
    print(f"  OK: t5xxl_fp16.safetensors")

if not os.path.exists(ae):
    print("  VAE ダウンロード中...")
    run(f"huggingface-cli download black-forest-labs/FLUX.1-dev ae.safetensors --local-dir {MODEL_DIR} --token {HF_TOKEN}")
else:
    print(f"  OK: ae.safetensors")

# =====================================================
# Step 3: dataset.toml 生成
# =====================================================
banner("Step 3: dataset.toml 生成")

toml_content = f"""[general]
caption_extension = ".txt"
keep_tokens = 1

[[datasets]]
resolution = 1024
batch_size = 1
enable_bucket = false

  [[datasets.subsets]]
  image_dir = "{DATASET_DIR}"
  num_repeats = 5

  [[datasets.subsets]]
  image_dir = "{REG_DIR}"
  num_repeats = 1
  is_reg = true
"""

with open(DATASET_TOML, "w") as f:
    f.write(toml_content)

print(f"  OK: {DATASET_TOML}")
print(f"  enable_bucket = false → 1024x1024固定")

# =====================================================
# Step 4: 出力ディレクトリ書き込みテスト
# =====================================================
banner("Step 4: 出力ディレクトリ書き込みテスト")
os.makedirs(OUTPUT_DIR, exist_ok=True)
test = os.path.join(OUTPUT_DIR, ".write_test")
with open(test, "w") as f:
    f.write("ok")
os.remove(test)
print(f"  OK: 書き込みテスト成功 → {OUTPUT_DIR}")

# =====================================================
# Step 5: ComfyUI停止（VRAM確保）
# =====================================================
banner("Step 5: VRAM確保")
run("pkill -f 'comfy' 2>/dev/null", check=False, capture_output=True)
run("pkill -f 'main.py' 2>/dev/null", check=False, capture_output=True)
time.sleep(3)
print("  OK")

# =====================================================
# Step 6: 学習開始
# =====================================================
banner("Step 6: LoRA学習開始")

print(f"""
  設定サマリー:
    トリガーワード : URDP001
    学習画像       : {len(imgs)}枚 × 5repeats = {len(imgs)*5}ステップ/epoch
    正則化画像     : {len(regs)}枚
    ステップ数     : 2000
    network_dim    : 16 / alpha: 8
    LoRA+比率      : 16
    learning_rate  : 1e-4 (cosine_with_restarts)
    解像度         : 1024x1024（bucket無効）
    fp8_base       : 有効（VRAM節約）
    出力先         : {OUTPUT_DIR}
""")

train_cmd = f"""accelerate launch \\
  --mixed_precision bf16 \\
  --num_cpu_threads_per_process 1 \\
  {KOHYA_DIR}/flux_train_network.py \\
  --pretrained_model_name_or_path {flux_model} \\
  --clip_l {clip_l} \\
  --ae {ae} \\
  --t5xxl {t5xxl} \\
  --cache_latents_to_disk \\
  --cache_text_encoder_outputs \\
  --cache_text_encoder_outputs_to_disk \\
  --save_model_as safetensors \\
  --sdpa \\
  --persistent_data_loader_workers \\
  --max_data_loader_n_workers 2 \\
  --seed 42 \\
  --gradient_checkpointing \\
  --mixed_precision bf16 \\
  --save_precision bf16 \\
  --network_module networks.lora_flux \\
  --network_dim 16 \\
  --network_alpha 8 \\
  --network_args "loraplus_lr_ratio=16" \\
  --optimizer_type adamw8bit \\
  --learning_rate 1e-4 \\
  --lr_scheduler cosine_with_restarts \\
  --lr_warmup_steps 50 \\
  --fp8_base \\
  --timestep_sampling shift \\
  --discrete_flow_shift 3.1582 \\
  --model_prediction_type raw \\
  --guidance_scale 1.0 \\
  --max_train_steps 2000 \\
  --save_every_n_steps 200 \\
  --output_dir {OUTPUT_DIR} \\
  --output_name URDP001_v2 \\
  --dataset_config {DATASET_TOML} \\
  --sample_every_n_steps 200 \\
  --sample_sampler euler \\
  --sample_prompts /tmp/urdp001_sample_prompts.txt \\
  --log_with tensorboard \\
  --logging_dir {OUTPUT_DIR}/logs"""

# サンプルプロンプト（lash/eye関連ワードなし）
sample_prompts = """URDP001, product on white background, studio lighting, centered composition --d 42 --w 1024 --h 1024 --s 20 --cfg 3.5
URDP001, held in a hand, light gray background, natural indoor lighting --d 42 --w 1024 --h 1024 --s 20 --cfg 3.5
URDP001, standing upright on a surface, neutral background, soft lighting --d 42 --w 1024 --h 1024 --s 20 --cfg 3.5
"""
with open("/tmp/urdp001_sample_prompts.txt", "w") as f:
    f.write(sample_prompts)

os.chdir(KOHYA_DIR)
os.execv("/bin/bash", ["/bin/bash", "-c", train_cmd])

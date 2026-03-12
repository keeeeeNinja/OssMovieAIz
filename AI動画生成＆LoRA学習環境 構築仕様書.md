0. このドキュメントについて
本仕様書はClaude Codeが読み取り、RunPod GPU Cloud上でSSH経由で実行することを前提に書かれている。各ステップには実行コマンド、成功判定条件、失敗時のフォールバックを明記する。
1. プロジェクト概要
項目内容目的Wan 2.1 14Bモデルによる動画生成環境（T2V + I2V）の構築、及びLoRA学習パイプラインの整備実行場所RunPod GPU Cloud（SSH接続）ベースOSUbuntu 22.04+GPUNVIDIA RTX 4090 / 3090（VRAM 24GB）永続ストレージ/workspace（RunPod Network Volume）推奨容量150GB以上
2. ディレクトリ構成（すべて /workspace 配下）
/workspace/
├── ComfyUI/
│   ├── models/
│   │   ├── diffusion_models/    # Wan 2.1 GGUF + fp8/fp16モデル
│   │   ├── text_encoders/       # T5 (umt5-xxl)
│   │   ├── vae/                 # Wan 2.1 VAE
│   │   ├── clip_vision/         # CLIP Vision (I2V用)
│   │   └── loras/               # 学習済みLoRA配置先
│   └── custom_nodes/
│       ├── ComfyUI-Manager/
│       └── ComfyUI-GGUF/
├── diffusion-pipe/
│   ├── models/
│   │   └── wan/                 # 学習用フルモデル
│   ├── data/
│   │   └── input/               # 学習データセット（画像+キャプション）
│   ├── examples/                # TOML設定ファイル
│   └── output/                  # 学習済みLoRA出力先
├── musubi-tuner/
│   ├── models/                  # 学習用モデル（diffusion-pipeと共有可）
│   ├── dataset/                 # データセットTOML + 素材
│   └── output/                  # 学習済みLoRA出力先
└── datasets/
    ├── images/                  # 素材画像（共通）
    ├── videos/                  # 素材動画（共通）
    └── captions/                # キャプションtxt（共通）
3. フェーズ1：動画生成環境の構築
Step 1-1: GPU・システム確認

# 実行
nvidia-smi
python3 --version
nvcc --version

成功条件: nvidia-smi でGPU名（RTX 4090/3090等）とDriver Version、CUDA Versionが表示される。Python 3.10以上。
失敗時: nvidia-smi が command not found → RunPodテンプレートがGPU対応か確認を促すメッセージを出して停止。
Step 1-2: ComfyUIインストール

cd /workspace
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

成功条件: pip install が正常終了（exit code 0）。
次に:
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
git clone https://github.com/city96/ComfyUI-GGUF.git
cd ComfyUI-GGUF && pip install -r requirements.txt

成功条件: 3つのディレクトリが存在し、それぞれに .git フォルダがある。
Step 1-3: モデルダウンロード
T2V用（Text-to-Video）GGUFモデル:

cd /workspace/ComfyUI/models/diffusion_models
# Q5_K_Mを推奨（品質とVRAMのバランス、約10.8GB）
wget https://huggingface.co/city96/Wan2.1-T2V-14B-gguf/resolve/main/wan2.1_t2v_14B-Q5_K_M.gguf

I2V用（Image-to-Video）GGUFモデル:
wget https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/wan2.1_i2v_480p_14B-Q5_K_M.gguf

Text Encoder（T5）:
cd /workspace/ComfyUI/models/text_encoders
wget https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors

VAE:
cd /workspace/ComfyUI/models/vae
wget https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors

CLIP Vision（I2V用）:
cd /workspace/ComfyUI/models/clip_vision
wget https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors

成功条件: 各ファイルが存在し、サイズが0でないこと。
ls -lh /workspace/ComfyUI/models/diffusion_models/*.gguf
ls -lh /workspace/ComfyUI/models/text_encoders/*.safetensors
ls -lh /workspace/ComfyUI/models/vae/*.safetensors
ls -lh /workspace/ComfyUI/models/clip_vision/*.safetensors

失敗時: wget が403/404 → Hugging Faceのリポジトリ名・ファイル名が変更された可能性。huggingface-cli download にフォールバック。
Step 1-4: 起動確認
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 &
sleep 15
curl -s http://localhost:8188/ | head -5

成功条件: curlでHTMLレスポンスが返る。ブラウザから http://<RunPod公開IP>:8188 でUI表示。
失敗時: ポートが開いていない → RunPodのHTTP Port設定で8188を公開しているか確認。CUDAエラー → PyTorchとCUDAのバージョン不一致の可能性。

4. フェーズ2：LoRA学習環境の整備
ツールA: diffusion-pipe
Step 2A-1: インストール
cd /workspace
git clone --recursive https://github.com/tdrussell/diffusion-pipe.git
cd diffusion-pipe
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

成功条件: pip install が正常終了。python -c "import torch; print(torch.cuda.is_available())" が True。
注意: flash-attnのビルドに時間がかかる場合がある（10〜15分）。タイムアウトしないこと。
Step 2A-2: 学習用モデルのダウンロード
cd /workspace/diffusion-pipe
mkdir -p models/wan
# T2V学習にはフルモデルが必要（GGUFではなくオリジナル）
huggingface-cli download Wan-AI/Wan2.1-T2V-14B --local-dir models/wan/Wan2.1-T2V-14B

注意: フルモデルは約27GB。ストレージ残量を確認してからダウンロード。
df -h /workspace

Step 2A-3: データセットディレクトリの作成
mkdir -p /workspace/datasets/images
mkdir -p /workspace/datasets/videos
mkdir -p /workspace/datasets/captions

Step 2A-4: 設定ファイルの作成
dataset.toml (/workspace/diffusion-pipe/examples/wan_dataset.toml):
[general]
resolution = [512, 512]
caption_extension = ".txt"
batch_size = 1
enable_bucket = true

[[datasets]]
image_directory = "/workspace/datasets/images"
caption_directory = "/workspace/datasets/captions"
num_repeats = 5
frame_buckets = [1, 33]

学習設定 (/workspace/diffusion-pipe/examples/wan_t2v_lora.toml):
[model]
type = "wan"
ckpt_path = "/workspace/diffusion-pipe/models/wan/Wan2.1-T2V-14B"
dtype = "bfloat16"
transformer_dtype = "float8"
timestep_sample_method = "logit_normal"

[adapter]
type = "lora"
rank = 32
alpha = 16
dtype = "bfloat16"

[optimizer]
type = "adamw"
lr = 2e-4
weight_decay = 0.01

[training]
batch_size = 1
epochs = 50
save_every_n_epochs = 10
gradient_checkpointing = true
mixed_precision = "bf16"
output_dir = "/workspace/diffusion-pipe/output"

[advanced]
blocks_to_swap = 20

Step 2A-5: 学習実行コマンド
cd /workspace/diffusion-pipe
NCCL_P2P_DISABLE="1" NCCL_IB_DISABLE="1" \
deepspeed --num_gpus=1 train.py --deepspeed \
  --config examples/wan_t2v_lora.toml

echo "=== LoRA TRAINING COMPLETE (diffusion-pipe) ===" >> /workspace/training.log
date >> /workspace/training.log

成功条件: output/ ディレクトリに adapter_model.safetensors が生成される。
ツールB: musubi-tuner
Step 2B-1: インストール
cd /workspace
git clone --recursive https://github.com/kohya-ss/musubi-tuner.git
cd musubi-tuner
python -m venv venv
source venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -e .
pip install xformers

成功条件: pip install -e . が正常終了。
Step 2B-2: 学習用モデルの準備
cd /workspace/musubi-tuner
mkdir -p models/diffusion_models models/text_encoders models/vae

# フルモデルが diffusion-pipe 側に既にあれば、シンボリックリンクで容量節約
ln -s /workspace/diffusion-pipe/models/wan/Wan2.1-T2V-14B /workspace/musubi-tuner/models/wan_t2v

# T5 encoder
wget -P models/text_encoders https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P/resolve/main/models_t5_umt5-xxl-enc-bf16.pth

# VAE（ComfyUI側と共有）
ln -s /workspace/ComfyUI/models/vae/wan_2.1_vae.safetensors /workspace/musubi-tuner/models/vae/wan_2.1_vae.safetensors

Step 2B-3: データセット設定
dataset.toml (/workspace/musubi-tuner/dataset/dataset.toml):
[general]
resolution = [512, 512]
caption_extension = ".txt"
batch_size = 1
enable_bucket = true

[[datasets]]
image_dir = "/workspace/datasets/images"
num_repeats = 5

Step 2B-4: 学習実行コマンド
cd /workspace/musubi-tuner
source venv/bin/activate

accelerate launch --num_cpu_threads_per_process 1 \
  src/musubi_tuner/wan_train_network.py \
  --task t2v-14B \
  --dit /workspace/musubi-tuner/models/wan_t2v \
  --vae /workspace/musubi-tuner/models/vae/wan_2.1_vae.safetensors \
  --t5 /workspace/musubi-tuner/models/text_encoders/models_t5_umt5-xxl-enc-bf16.pth \
  --dataset_config /workspace/musubi-tuner/dataset/dataset.toml \
  --sdpa \
  --mixed_precision fp16 \
  --fp8_base \
  --optimizer_type adamw \
  --learning_rate 2e-4 \
  --gradient_checkpointing \
  --network_module networks.lora_wan \
  --network_dim 32 \
  --network_alpha 16 \
  --timestep_sampling shift \
  --discrete_flow_shift 7.0 \
  --max_train_epochs 50 \
  --save_every_n_epochs 10 \
  --seed 42 \
  --blocks_to_swap 20 \
  --output_dir /workspace/musubi-tuner/output \
  --output_name wan21_lora

echo "=== LoRA TRAINING COMPLETE (musubi-tuner) ===" >> /workspace/training.log
date >> /workspace/training.log

成功条件: output/ に wan21_lora_epochXX.safetensors が生成される。

5. フェーズ3：学習済みLoRAの検証
# ComfyUI の lorasディレクトリにコピー
cp /workspace/diffusion-pipe/output/*/adapter_model.safetensors \
   /workspace/ComfyUI/models/loras/lora_diffpipe.safetensors

cp /workspace/musubi-tuner/output/wan21_lora_epoch50.safetensors \
   /workspace/ComfyUI/models/loras/lora_musubi.safetensors

ComfyUIを再起動し、LoRA Loaderノードで各LoRAを読み込んでT2V/I2Vワークフローで生成テスト。
6. 制約・運用ルール

学習完了通知: 学習完了時に /workspace/training.log にタイムスタンプ付きログを出力
ストレージ管理: df -h /workspace で残容量を都度確認。80%超えたら古いチェックポイントを削除
インスタンス停止: 学習完了後は sudo shutdown -h now でコスト削減可能
エラー対応: 各ステップで exit code != 0 の場合、エラーログを解析し、エラー対応表を参照


パート2：CLAUDE.md テンプレート

# CLAUDE.md — AI動画生成＆LoRA学習プロジェクト

## プロジェクト概要
RunPod GPU Cloud上でWan 2.1 14Bの動画生成環境とLoRA学習環境を構築するプロジェクト。

## 実行環境
- RunPod GPU Cloud (SSH接続)
- Ubuntu 22.04+, RTX 4090/3090 (VRAM 24GB)
- 永続ストレージ: /workspace (Network Volume)
- Python 3.10+, CUDA 12.x

## 作業ルール

### 絶対ルール
1. すべてのインストール・ダウンロードは `/workspace` 配下で行う（永続化のため）
2. 各ステップ実行後に成功条件を検証してから次へ進む
3. `pip install` には仮想環境を使うか、`--break-system-packages` を付ける
4. 大容量ダウンロード前に `df -h /workspace` でストレージ残量を確認する
5. エラー発生時は自己修正を3回まで試行、解決不能なら現状を報告して停止

### コマンド実行方針
- 長時間コマンド（モデルDL、学習等）は `nohup` やバックグラウンド実行を使わず、完了を待つ
- wget/huggingface-cli が失敗した場合は3回リトライ
- GPUメモリエラー（OOM）が出たら `blocks_to_swap` を5ずつ増やして再試行

### 進捗報告
- 各フェーズ/ステップ完了時に「✅ Step X-X 完了」と報告
- エラー時は「❌ Step X-X 失敗: [エラー要約]」と報告
- ストレージ使用量は大容量操作の前後に報告

### ファイル命名規則
- LoRA出力: `{purpose}_{tool}_{date}.safetensors`（例: `style_diffpipe_20250311.safetensors`）
- ログ: `/workspace/training.log` に追記

## ディレクトリ構成
```
/workspace/
├── ComfyUI/           # 動画生成UI
├── diffusion-pipe/    # LoRA学習ツールA
├── musubi-tuner/      # LoRA学習ツールB
└── datasets/          # 共通データセット
```

## 既知の問題と対応
- ComfyUI-GGUF が最新のComfyUIと互換性問題を起こすことがある → 両方を最新にする
- diffusion-pipe の flash-attn ビルドが失敗する場合 → `--no-build-isolation` を試す
- musubi-tuner で LoRA が ComfyUI で効かない場合 → `convert_lora.py` で変換が必要な場合がある
- RTX 4090 では `transformer_dtype = 'float8'` で学習速度が30-40x向上
- Wan 2.1 の T2V で学習したLoRAは I2V でも使えることが多い（逆は品質低下しやすい）

パート3：想定エラー対応表

#エラー内容発生タイミング原因対応E01nvidia-smi: command not foundStep 1-1NVIDIAドライバ未インストール/GPUなしテンプレートRunPodのPodテンプレートをGPU対応（PyTorch等）に変更して再デプロイ。処理を停止して報告。E02CUDA out of memory (OOM)ComfyUI動画生成時VRAM不足GGUFの量子化レベルを下げる（Q5→Q4→Q3）。または生成解像度を下げる（720P→480P）。E03wget 403/404モデルダウンロード時URLが変更された/認証が必要huggingface-cli download に切り替え。huggingface-cli login が必要な場合はトークン入力を促す。E04ModuleNotFoundError: No module named 'xxx'ComfyUI起動時依存関係の不足pip install xxx で不足モジュールをインストール。E05RuntimeError: CUDA error: no kernel image学習実行時PyTorchとCUDAのバージョン不一致pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124 でCUDA 12.4対応版を再インストール。E06flash_attn ビルドエラーdiffusion-pipe インストール時nvcc不足/バージョン不一致pip install flash-attn --no-build-isolation を試す。それでもダメなら conda install -c nvidia cuda-nvcc を実行後に再試行。E07OOM during trainingLoRA学習時batch_sizeが大きい/解像度が高い/blocks_to_swapが小さいblocks_to_swap を現在値+5に増やす。それでもダメなら解像度を480x272に下げる。E08LoRAがComfyUIで効かないフェーズ3検証時モデル形式の不一致/LoRA適用方法のミスmusubi-tunerの場合は convert_lora.py で変換。diffusion-pipeの場合はComfyUI側のLoRA Loader設定を確認。E09No space left on deviceダウンロード/学習時ストレージ容量不足du -sh /workspace/* で大容量フォルダを特定。古いチェックポイント（epoch*/）を削除。E10Connection refused (ComfyUI)Step 1-4ポートが公開されていない/起動に時間がかかっているsleep 30 で待つ。RunPodダッシュボードでHTTP Port 8188が設定されているか確認を促す。E11deepspeed コマンドが見つからないdiffusion-pipe学習時deepspeed未インストールpip install deepspeed を実行。E12git submodule update 失敗diffusion-pipe/musubi-tunerサブモジュールの初期化忘れgit submodule init && git submodule update を実行。
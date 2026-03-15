#!/bin/bash
set -e
echo '============================================'
echo '  ComfyUI + Wan 2.1 I2V Auto Setup'
echo '  + SageAttention / TeaCache / MP4出力'
echo '============================================'

# --- 1. SSH key (Claude Codeからリモート操作する場合) ---
mkdir -p /root/.ssh
printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINIWVCzSc3DZBiFpqPrecairHRuFO5wkNBJlrvsVB4Cy a@b\n' > /root/.ssh/authorized_keys
chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys
echo '[1/8] SSH key configured'

# --- 2. ComfyUI ---
cd /workspace
if [ ! -d "ComfyUI" ]; then
  git clone https://github.com/comfyanonymous/ComfyUI.git
fi
cd ComfyUI
git checkout master 2>/dev/null || true
git pull origin master 2>/dev/null || true
pip install -q -r requirements.txt
echo '[2/8] ComfyUI installed (latest)'

# --- 3. Custom Nodes ---
cd /workspace/ComfyUI/custom_nodes

# ComfyUI-Manager
[ ! -d "ComfyUI-Manager" ] && git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# ComfyUI-GGUF（GGUFモデル読み込み）
[ ! -d "ComfyUI-GGUF" ] && git clone https://github.com/city96/ComfyUI-GGUF.git
cd /workspace/ComfyUI/custom_nodes/ComfyUI-GGUF && pip install -q -r requirements.txt

# KJNodes（SageAttention + TeaCache）
cd /workspace/ComfyUI/custom_nodes
[ ! -d "ComfyUI-KJNodes" ] && git clone https://github.com/kijai/ComfyUI-KJNodes.git
cd /workspace/ComfyUI/custom_nodes/ComfyUI-KJNodes && pip install -q -r requirements.txt 2>/dev/null || true

# VideoHelperSuite（MP4出力用）
cd /workspace/ComfyUI/custom_nodes
[ ! -d "ComfyUI-VideoHelperSuite" ] && git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
cd /workspace/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && pip install -q -r requirements.txt 2>/dev/null || true

echo '[3/8] Custom nodes installed (Manager, GGUF, KJNodes, VideoHelperSuite)'

# --- 4. SageAttention (pip) ---
echo '[4/8] Installing SageAttention...'
pip install -q sageattention 2>/dev/null || {
  echo '  SageAttention pip install failed, trying from source...'
  cd /workspace
  if [ ! -d "SageAttention" ]; then
    git clone https://github.com/thu-ml/SageAttention.git
  fi
  cd SageAttention
  pip install -q -e . 2>/dev/null || echo '  WARNING: SageAttention install failed. Will run without it.'
}
echo '[4/8] SageAttention done'

# --- 5. Wan 2.1 I2V Models (parallel download) ---
echo '[5/8] Downloading Wan 2.1 I2V models...'

mkdir -p /workspace/ComfyUI/models/diffusion_models
mkdir -p /workspace/ComfyUI/models/text_encoders
mkdir -p /workspace/ComfyUI/models/clip_vision
mkdir -p /workspace/ComfyUI/models/vae

cd /workspace/ComfyUI/models/diffusion_models
[ ! -f "wan2.1-i2v-14b-480p-Q5_K_M.gguf" ] && \
  wget -q https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/wan2.1-i2v-14b-480p-Q5_K_M.gguf &
PID_W1=$!

cd /workspace/ComfyUI/models/text_encoders
[ ! -f "umt5_xxl_fp8_e4m3fn_scaled.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors &
PID_W2=$!

cd /workspace/ComfyUI/models/vae
[ ! -f "wan_2.1_vae.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors &
PID_W3=$!

cd /workspace/ComfyUI/models/clip_vision
[ ! -f "clip_vision_h.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors &
PID_W4=$!

# Wait for all downloads
echo 'Waiting for all downloads to complete...'
wait $PID_W1 $PID_W2 $PID_W3 $PID_W4
echo '[5/8] All models downloaded'

# --- 6. ffmpeg確認（MP4出力に必要） ---
echo '[6/8] Checking ffmpeg...'
if ! command -v ffmpeg &> /dev/null; then
  apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null 2>&1
  echo '  ffmpeg installed'
else
  echo '  ffmpeg already available'
fi

# --- 7. Verify ---
echo '[7/8] Verifying files...'
echo '--- Diffusion Models ---'
ls -lh /workspace/ComfyUI/models/diffusion_models/*.gguf
echo '--- Text Encoders ---'
ls -lh /workspace/ComfyUI/models/text_encoders/*.safetensors
echo '--- VAE ---'
ls -lh /workspace/ComfyUI/models/vae/*.safetensors
echo '--- CLIP Vision ---'
ls -lh /workspace/ComfyUI/models/clip_vision/*.safetensors
echo '--- Custom Nodes ---'
ls -d /workspace/ComfyUI/custom_nodes/ComfyUI-Manager \
      /workspace/ComfyUI/custom_nodes/ComfyUI-GGUF \
      /workspace/ComfyUI/custom_nodes/ComfyUI-KJNodes \
      /workspace/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite 2>/dev/null
echo '--- SageAttention ---'
python3 -c "import sageattention; print('  SageAttention:', sageattention.__version__)" 2>/dev/null || echo '  SageAttention: not available'
nvidia-smi | head -4
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"

# --- 8. Start ComfyUI ---
cd /workspace/ComfyUI
python3 main.py --listen 0.0.0.0 --port 8188 --use-sage-attention > /workspace/comfyui.log 2>&1 &
echo '[8/8] ComfyUI starting on port 8188...'
sleep 25
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/)
if [ "$HTTP_CODE" = "200" ]; then
  echo ''
  echo '============================================'
  echo '  SETUP COMPLETE! ComfyUI is ready.'
  echo '  Model: Wan 2.1 I2V 14B (Q5_K_M)'
  echo '  Nodes: GGUF, KJNodes, VideoHelperSuite'
  echo '  Accel: SageAttention + TeaCache'
  echo '  Output: MP4 via VHS_VideoCombine'
  echo '  Open Port 8188 link in RunPod dashboard.'
  echo '============================================'
else
  echo 'ComfyUI not responding yet. Check: tail -30 /workspace/comfyui.log'
fi

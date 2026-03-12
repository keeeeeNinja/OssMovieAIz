#!/bin/bash
set -e
echo '============================================'
echo '  ComfyUI + Wan 2.1 I2V + HunyuanVideo'
echo '  Auto Setup Script'
echo '============================================'

# --- 1. SSH key (Claude Codeからリモート操作する場合) ---
mkdir -p /root/.ssh
printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINIWVCzSc3DZBiFpqPrecairHRuFO5wkNBJlrvsVB4Cy a@b\n' > /root/.ssh/authorized_keys
chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys
echo '[1/7] SSH key configured'

# --- 2. ComfyUI ---
cd /workspace
if [ ! -d "ComfyUI" ]; then
  git clone https://github.com/comfyanonymous/ComfyUI.git
fi
cd ComfyUI
pip install -q -r requirements.txt
echo '[2/7] ComfyUI installed'

# --- 3. Custom Nodes ---
cd /workspace/ComfyUI/custom_nodes
[ ! -d "ComfyUI-Manager" ] && git clone https://github.com/ltdrdata/ComfyUI-Manager.git
[ ! -d "ComfyUI-GGUF" ] && git clone https://github.com/city96/ComfyUI-GGUF.git
cd ComfyUI-GGUF && pip install -q -r requirements.txt
echo '[3/7] Custom nodes installed'

# --- 4. Wan 2.1 I2V Models (parallel download) ---
echo '[4/7] Downloading Wan 2.1 I2V models...'

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

echo '[4/7] Wan downloads started in background'

# --- 5. HunyuanVideo Models (parallel download) ---
echo '[5/7] Downloading HunyuanVideo models...'

cd /workspace/ComfyUI/models/diffusion_models
[ ! -f "hunyuan-video-t2v-720p-Q4_K_M.gguf" ] && \
  wget -q https://huggingface.co/city96/HunyuanVideo-gguf/resolve/main/hunyuan-video-t2v-720p-Q4_K_M.gguf &
PID_H1=$!

cd /workspace/ComfyUI/models/text_encoders
[ ! -f "clip_l.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/text_encoders/clip_l.safetensors &
PID_H2=$!

[ ! -f "llava_llama3_fp8_scaled.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/text_encoders/llava_llama3_fp8_scaled.safetensors &
PID_H3=$!

cd /workspace/ComfyUI/models/clip_vision
[ ! -f "llava_llama3_vision.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/clip_vision/llava_llama3_vision.safetensors &
PID_H4=$!

cd /workspace/ComfyUI/models/vae
[ ! -f "hunyuan_video_vae_bf16.safetensors" ] && \
  wget -q https://huggingface.co/Comfy-Org/HunyuanVideo_repackaged/resolve/main/split_files/vae/hunyuan_video_vae_bf16.safetensors &
PID_H5=$!

echo '[5/7] HunyuanVideo downloads started in background'

# Wait for all downloads
echo 'Waiting for all downloads to complete...'
wait $PID_W1 $PID_W2 $PID_W3 $PID_W4 $PID_H1 $PID_H2 $PID_H3 $PID_H4 $PID_H5
echo '[5/7] All models downloaded'

# --- 6. Verify ---
echo '[6/7] Verifying files...'
echo '--- Diffusion Models ---'
ls -lh /workspace/ComfyUI/models/diffusion_models/*.gguf
echo '--- Text Encoders ---'
ls -lh /workspace/ComfyUI/models/text_encoders/*.safetensors
echo '--- VAE ---'
ls -lh /workspace/ComfyUI/models/vae/*.safetensors
echo '--- CLIP Vision ---'
ls -lh /workspace/ComfyUI/models/clip_vision/*.safetensors
nvidia-smi | head -4
python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"

# --- 7. Start ComfyUI ---
cd /workspace/ComfyUI
python3 main.py --listen 0.0.0.0 --port 8188 > /workspace/comfyui.log 2>&1 &
echo '[7/7] ComfyUI starting on port 8188...'
sleep 25
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/)
if [ "$HTTP_CODE" = "200" ]; then
  echo ''
  echo '============================================'
  echo '  SETUP COMPLETE! ComfyUI is ready.'
  echo '  Available models:'
  echo '    - Wan 2.1 I2V 14B (Q5_K_M)'
  echo '    - HunyuanVideo 8.3B (Q4_K_M)'
  echo '  Open Port 8188 link in RunPod dashboard.'
  echo '============================================'
else
  echo 'ComfyUI not responding yet. Check: tail -30 /workspace/comfyui.log'
fi

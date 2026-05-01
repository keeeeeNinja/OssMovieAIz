#!/usr/bin/env python3
"""受講生向け 一発セットアップ: 商用利用 OK のモデル一式を Network Volume に配置。

実行内容:
  - Flux Schnell Q8_0 GGUF (Apache 2.0)
  - Flux VAE ae.safetensors (Schnell repo / Apache 2.0、HF token 不要)
  - Flux text encoders: t5xxl_fp8_e4m3fn + clip_l (商用 OK)
  - Wan 2.1 I2V 14B Q5_K_M GGUF + 関連 (Apache 2.0)
  - Qwen3-TTS-12Hz-1.7B-Base + Tokenizer (Apache 2.0、HF キャッシュへ)

旧 setup_comfyui.sh の置き換え。Pod 経由で書き込むので Mac→S3 直送より十数倍速い。
1 セッションで一時 Pod を立てて全 DL → Pod 自動削除。

Usage:
  python3 scripts/bootstrap_volume.py
  python3 scripts/bootstrap_volume.py --skip-tts        # TTS は不要なら除外
  python3 scripts/bootstrap_volume.py --keep-pod         # デバッグ用に Pod 残す
"""
import argparse
import os
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--skip-tts", action="store_true", help="Qwen3-TTS のDLをスキップ")
    p.add_argument("--skip-images", action="store_true", help="Flux/Wan のDLをスキップ")
    p.add_argument("--keep-pod", action="store_true", help="完了後も Pod を残す")
    args = p.parse_args()

    # ---- ファイル URL ----
    bulk = []
    if not args.skip_images:
        bulk += [
            # Flux Schnell GGUF (Q8_0, Apache 2.0)
            "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q8_0.gguf"
            "=>/runpod-volume/ComfyUI/models/unet/flux1-schnell-Q8_0.gguf",
            # Flux VAE (Schnell repo = Apache 2.0、HF token 不要)
            "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors"
            "=>/runpod-volume/ComfyUI/models/vae/ae.safetensors",
            # Flux text encoders (Apache 2.0 / MIT)
            "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors"
            "=>/runpod-volume/ComfyUI/models/text_encoders/t5xxl_fp8_e4m3fn.safetensors",
            "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors"
            "=>/runpod-volume/ComfyUI/models/text_encoders/clip_l.safetensors",
            # Wan 2.1 I2V (Apache 2.0)
            "https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/wan2.1-i2v-14b-480p-Q5_K_M.gguf"
            "=>/runpod-volume/ComfyUI/models/unet/wan2.1-i2v-14b-480p-Q5_K_M.gguf",
            "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
            "=>/runpod-volume/ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"
            "=>/runpod-volume/ComfyUI/models/vae/wan_2.1_vae.safetensors",
            "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors"
            "=>/runpod-volume/ComfyUI/models/clip_vision/clip_vision_h.safetensors",
        ]

    # ---- HF snapshot (TTS) ----
    hf_snapshots = []
    if not args.skip_tts:
        hf_snapshots += [
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            "Qwen/Qwen3-TTS-Tokenizer-12Hz",
        ]

    if not bulk and not hf_snapshots:
        sys.exit("❌ 何もすることがありません（--skip-* で全部除外しました）")

    # upload_via_pod.py を呼び出し（1 Pod セッションで全部 DL）
    here = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, os.path.join(here, "upload_via_pod.py")]
    if bulk:
        cmd += ["--bulk"] + bulk
    if hf_snapshots:
        cmd += ["--hf-snapshot"] + hf_snapshots
    if args.keep_pod:
        cmd += ["--keep-pod"]

    print("📦 Bootstrap 開始")
    print(f"  画像系: {'スキップ' if args.skip_images else f'{len(bulk)} ファイル'}")
    print(f"  TTS:    {'スキップ' if args.skip_tts else f'{len(hf_snapshots)} HF repo'}")
    print(f"  実行: {' '.join(cmd[:3])} ... ({len(cmd)} args)")
    print()
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())

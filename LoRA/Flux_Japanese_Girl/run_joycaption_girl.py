#!/usr/bin/env python3
"""
JoyCaption で Flux_Japanese_Girl データセットのキャプション生成
トリガーワード: ohwx woman
"""

import os
import torch
from pathlib import Path
from PIL import Image
from transformers import (
    AutoProcessor,
    LlavaForConditionalGeneration,
)

# HF Token
with open("/tmp/hf_token.txt") as f:
    hf_token = f.read().strip()
os.environ["HF_TOKEN"] = hf_token

IMAGE_DIR = "/workspace/datasets/Flux_Japanese_Girl"
TRIGGER = "ohwx woman"
MODEL_ID = "fancyfeast/llama-joycaption-alpha-two-hf-llava"

CAPTION_PROMPT = (
    f"Write a detailed caption for this image. "
    f"Start the caption with '{TRIGGER}'. "
    f"Describe the person's appearance, clothing, pose, expression, and background."
)

print("Loading JoyCaption model...")
processor = AutoProcessor.from_pretrained(MODEL_ID, token=hf_token, use_fast=False)
model = LlavaForConditionalGeneration.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    token=hf_token,
)
model.eval()
print("Model loaded.")

image_paths = sorted(Path(IMAGE_DIR).glob("*.png"))
print(f"Found {len(image_paths)} images.")

for img_path in image_paths:
    caption_path = img_path.with_suffix(".txt")
    if caption_path.exists():
        print(f"Skip (already exists): {img_path.name}")
        continue

    image = Image.open(img_path).convert("RGB")

    messages = [
        {"role": "user", "content": f"<image>\n{CAPTION_PROMPT}"}
    ]
    prompt = processor.apply_chat_template(
        messages, add_generation_prompt=True
    )
    inputs = processor(images=image, text=prompt, return_tensors="pt").to(
        model.device
    )

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
        )

    caption = processor.decode(
        output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
    ).strip()

    # トリガーワードが先頭にない場合は追加
    if not caption.lower().startswith(TRIGGER.lower()):
        caption = f"{TRIGGER}, {caption}"

    caption_path.write_text(caption)
    print(f"  [{img_path.name}] {caption[:80]}...")

print("\nAll captions generated!")

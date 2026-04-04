#!/usr/bin/env python3
"""
Wan 2.1 I2V Video Generator via ComfyUI on RunPod
Generates 13 beauty habit video clips sequentially.
"""

import json
import os
import random
import subprocess
import sys
import time
import tempfile

SSH_KEY = os.path.expanduser("~/.ssh/runpod_key")
HOST = "213.173.99.49"
PORT = 16558
COMFYUI_OUTPUT_DIR = "/workspace/ComfyUI/output"
LOCAL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../作業中動画")

NEGATIVE = "blurry, distorted, low quality, shaky, deformed hands, extra fingers, watermark, text overlay"

SCENES = [
    {
        "id": "S01", "image": "flux_C01.png", "prefix": "beauty_S01",
        "prompt": "She breathes softly, a gentle smile forming naturally, strands of hair swaying delicately in a light breeze. Slow dolly in toward her face. Soft natural window light casting warm highlights on her luminous skin. Airy and serene morning atmosphere, close-up portrait, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S02", "image": "flux_C02.png", "prefix": "beauty_S02",
        "prompt": "She gently presses her fingertips against her cheeks, examining her skin with quiet determination, eyelashes fluttering softly. Static shot. Soft diffused bathroom light from above casting gentle shadows on her bare face. Honest morning routine atmosphere, medium close-up, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S03", "image": "flux_C04.png", "prefix": "beauty_S03",
        "prompt": "She gently massages the creamy foam across her cheeks in slow circular motions, eyes softly closed in calm concentration. Slow push in from medium close-up to extreme close-up. Soft white bathroom lighting highlighting the texture of the foam against her skin. Clean fresh atmosphere, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S04", "image": "flux_C06.png", "prefix": "beauty_S04",
        "prompt": "A single droplet of golden serum falls slowly from the glass dropper tip, viscous liquid stretching and catching the light as it descends. Static macro shot. Bright clean studio lighting creating warm golden reflections in the liquid. Minimal elegant atmosphere, extreme macro, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S05", "image": "flux_C07.png", "prefix": "beauty_S05",
        "prompt": "She presses the moisturizer gently into her cheeks with soft circular motions, eyes closed in peaceful contentment, a faint smile on her lips. Slow pan right. Soft diffused daylight from left casting warm highlights on her dewy skin. Serene nurturing atmosphere, close-up, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S06", "image": "flux_C10.png", "prefix": "beauty_S06",
        "prompt": "She slides the gua sha tool slowly along her jawline with a gentle upward stroke, eyes closed in relaxed concentration. Slow dolly in. Warm candlelight casting soft amber glows on her face, the candle flame flickering subtly in the background. Intimate spa-like atmosphere, medium close-up, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S07", "image": "flux_C11.png", "prefix": "beauty_S07",
        "prompt": "She lies completely still with the sheet mask in place, chest rising and falling with slow deep breaths, her body sinking into relaxation. Slow pull back revealing her peaceful resting pose from above. Soft diffused ambient light from above. Calm restorative atmosphere, medium shot from above, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S08", "image": "flux_C13.png", "prefix": "beauty_S08",
        "prompt": "Steam rises gently from the coffee cup beside the open journal, the handwritten checklist resting still on the warm wooden surface. Slow tilt down from wide shot to close-up on the checklist. Warm morning light from window casting soft geometric shadows across the wooden desk. Cozy productive morning atmosphere, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S09", "image": "flux_C12.png", "prefix": "beauty_S09",
        "prompt": "She runs her fingers through her hair with a natural warm smile, gaze soft and confident as she looks at herself. Slow tracking shot from left to right. Warm morning light streaming through window casting golden highlights on her hair and white top. Joyful morning self-care atmosphere, medium shot, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S10", "image": "flux_C15.png", "prefix": "beauty_S10",
        "prompt": "The light shifts softly across her luminous skin, catching every subtle texture and highlighting the dewy glow in the gentle morning illumination. Very slow dolly in toward her cheek. Soft diffused natural morning light revealing the luminosity and clarity of her complexion. Beauty macro atmosphere, extreme close-up, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S11", "image": "flux_C16.png", "prefix": "beauty_S11",
        "prompt": "A genuine warm smile spreads across her face as she looks at her own reflection, shoulders relaxing with quiet inner confidence. Static shot. Soft bathroom morning light from above casting even warm illumination on her glowing face. Intimate self-affirming atmosphere, medium close-up, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S12", "image": "flux_C14.png", "prefix": "beauty_S12",
        "prompt": "Golden morning light wraps softly around her as she stands by the window, strands of hair catching the warm glow, a quiet sense of peace in her posture. Slow pull back revealing the full window frame with sunlight streaming in around her. Golden hour warm window light with soft rim lighting from behind. Radiant serene atmosphere, medium to wide shot, high quality, cinematic, detailed, 4K."
    },
    {
        "id": "S13", "image": "flux_C18.png", "prefix": "beauty_S13",
        "prompt": "She walks forward along the sun-dappled path, white dress swaying gently with each step, light filtering through the trees casting soft bokeh around her. Slow tracking shot following from behind as she moves away. Golden hour warm light streaming through forest trees creating lens flares and gentle atmospheric glow. Hopeful and free-spirited atmosphere, medium shot from behind, high quality, cinematic, detailed, 4K."
    },
]

WORKFLOW_TEMPLATE = """{
  "1": {
    "class_type": "UnetLoaderGGUF",
    "inputs": {
      "unet_name": "wan2.1-i2v-14b-480p-Q5_K_M.gguf"
    }
  },
  "2": {
    "class_type": "CLIPLoader",
    "inputs": {
      "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
      "type": "wan"
    }
  },
  "3": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "[PROMPT]",
      "clip": ["2", 0]
    }
  },
  "4": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "[NEGATIVE]",
      "clip": ["2", 0]
    }
  },
  "5": {
    "class_type": "CLIPVisionLoader",
    "inputs": {
      "clip_name": "clip_vision_h.safetensors"
    }
  },
  "6": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "[IMAGE_NAME]"
    }
  },
  "7": {
    "class_type": "CLIPVisionEncode",
    "inputs": {
      "crop": "center",
      "clip_vision": ["5", 0],
      "image": ["6", 0]
    }
  },
  "10": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "wan_2.1_vae.safetensors"
    }
  },
  "11": {
    "class_type": "WanVideoTeaCacheKJ",
    "inputs": {
      "model": ["1", 0],
      "rel_l1_thresh": 0.3,
      "start_percent": 0.1,
      "end_percent": 1.0,
      "cache_device": "offload_device",
      "coefficients": "i2v_480"
    }
  },
  "8": {
    "class_type": "WanImageToVideo",
    "inputs": {
      "positive": ["3", 0],
      "negative": ["4", 0],
      "vae": ["10", 0],
      "width": 480,
      "height": 832,
      "length": 81,
      "batch_size": 1,
      "clip_vision_output": ["7", 0],
      "start_image": ["6", 0]
    }
  },
  "12": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["11", 0],
      "positive": ["8", 0],
      "negative": ["8", 1],
      "latent_image": ["8", 2],
      "seed": [SEED_VALUE],
      "steps": 30,
      "cfg": 3.0,
      "sampler_name": "euler",
      "scheduler": "simple",
      "denoise": 1.0
    }
  },
  "13": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["12", 0],
      "vae": ["10", 0]
    }
  },
  "9": {
    "class_type": "VHS_VideoCombine",
    "inputs": {
      "images": ["13", 0],
      "frame_rate": 16,
      "loop_count": 0,
      "filename_prefix": "[OUTPUT_PREFIX]",
      "format": "video/h264-mp4",
      "pingpong": false,
      "save_output": true
    }
  }
}"""


def ssh(cmd, check=True):
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
                f"root@{HOST}", "-p", str(PORT), "-i", SSH_KEY, cmd]
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"SSH error: {result.stderr}", file=sys.stderr)
    return result.stdout.strip()


def scp_download(remote_path, local_path):
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(PORT), "-i", SSH_KEY,
           f"root@{HOST}:{remote_path}", local_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def submit_workflow(workflow: dict) -> str:
    payload = json.dumps({"prompt": workflow})
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(payload)
        tmp_local = f.name
    tmp_remote = "/tmp/wan_payload.json"
    scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(PORT), "-i", SSH_KEY,
               tmp_local, f"root@{HOST}:{tmp_remote}"]
    subprocess.run(scp_cmd, capture_output=True)
    os.unlink(tmp_local)
    out = ssh(f"curl -s -X POST http://localhost:8188/prompt -H 'Content-Type: application/json' -d @{tmp_remote}")
    try:
        resp = json.loads(out)
        if "error" in resp:
            print(f"  Workflow error: {resp['error']}", file=sys.stderr)
            return ""
        return resp.get("prompt_id", "")
    except Exception:
        print(f"  Submit error: {out}", file=sys.stderr)
        return ""


def poll_until_done(prompt_id: str, timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        out = ssh(f"curl -s 'http://localhost:8188/queue'", check=False)
        try:
            q = json.loads(out)
            running = len(q.get("queue_running", []))
            pending = len(q.get("queue_pending", []))
            if running == 0 and pending == 0:
                # Double-check via history
                hist_out = ssh(f"curl -s 'http://localhost:8188/history/{prompt_id}'", check=False)
                hist = json.loads(hist_out)
                if prompt_id in hist and hist[prompt_id].get("outputs"):
                    return True
        except Exception:
            pass
        elapsed = int(time.time() - start)
        print(f"  生成中... ({elapsed}秒経過)", flush=True)
        time.sleep(60)
    return False


def find_output_file(prefix: str) -> str:
    out = ssh(f"ls -t {COMFYUI_OUTPUT_DIR}/{prefix}*.mp4 2>/dev/null | head -1", check=False)
    return out.strip()


def build_workflow(scene: dict) -> dict:
    wf_str = WORKFLOW_TEMPLATE
    wf_str = wf_str.replace('"[PROMPT]"', json.dumps(scene["prompt"]))
    wf_str = wf_str.replace('"[NEGATIVE]"', json.dumps(NEGATIVE))
    wf_str = wf_str.replace('"[IMAGE_NAME]"', json.dumps(scene["image"]))
    wf_str = wf_str.replace('"[OUTPUT_PREFIX]"', json.dumps(scene["prefix"]))
    wf_str = wf_str.replace("[SEED_VALUE]", str(random.randint(1, 2**32)))
    return json.loads(wf_str)


def main():
    os.makedirs(LOCAL_OUTPUT_DIR, exist_ok=True)
    results = []

    for scene in SCENES:
        sid = scene["id"]
        local_file = os.path.join(LOCAL_OUTPUT_DIR, f"{scene['prefix']}_wan21.mp4")

        if os.path.exists(local_file):
            print(f"\n[{sid}] スキップ（既存）: {local_file}")
            results.append({"id": sid, "status": "skipped", "file": local_file})
            continue

        print(f"\n[{sid}] 生成開始 — {scene['image']}")
        print(f"  プロンプト: {scene['prompt'][:60]}...")

        wf = build_workflow(scene)
        prompt_id = submit_workflow(wf)
        if not prompt_id:
            print(f"  [エラー] ワークフロー投入失敗", file=sys.stderr)
            results.append({"id": sid, "status": "error"})
            continue

        print(f"  prompt_id: {prompt_id}")
        done = poll_until_done(prompt_id, timeout=900)

        if not done:
            print(f"  [エラー] タイムアウト", file=sys.stderr)
            results.append({"id": sid, "status": "timeout"})
            continue

        remote_file = find_output_file(scene["prefix"])
        if not remote_file:
            print(f"  [エラー] 出力ファイルが見つかりません", file=sys.stderr)
            results.append({"id": sid, "status": "error"})
            continue

        ok = scp_download(remote_file, local_file)
        if ok:
            print(f"  ✅ ダウンロード完了: {local_file}")
            results.append({"id": sid, "status": "ok", "file": local_file})
        else:
            print(f"  [エラー] ダウンロード失敗", file=sys.stderr)
            results.append({"id": sid, "status": "error"})

    print("\n" + "=" * 50)
    print("生成完了サマリー")
    print("=" * 50)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skip_count = sum(1 for r in results if r["status"] == "skipped")
    err_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    print(f"✅ 成功: {ok_count}  ⏭ スキップ: {skip_count}  ❌ エラー: {err_count}")
    for r in results:
        icon = {"ok": "✅", "skipped": "⏭", "error": "❌", "timeout": "⏱"}.get(r["status"], "?")
        print(f"  {icon} {r['id']}: {r.get('file', r['status'])}")


if __name__ == "__main__":
    main()

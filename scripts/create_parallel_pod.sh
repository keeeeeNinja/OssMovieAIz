#!/bin/bash
#
# 並列生成用Pod作成スクリプト（2台目以降）
#
# RunPod APIでVolume なしRTX 4090 Podを作成し、
# ComfyUI + Wan 2.1 I2Vの環境セットアップまで自動実行する。
#
# 使い方:
#   bash scripts/create_parallel_pod.sh
#   bash scripts/create_parallel_pod.sh --region EU-RO-1
#   bash scripts/create_parallel_pod.sh --gpu "NVIDIA GeForce RTX 4090"
#
set -euo pipefail

# --- 設定 ---
GPU_TYPE="NVIDIA GeForce RTX 4090"
REGION=""  # 空=Any region
SSH_KEY="$HOME/.ssh/id_ed25519"
SETUP_URL="https://raw.githubusercontent.com/keeeeeNinja/OssMovieAIz/master/setup_comfyui.sh"
SSH_MD="$(cd "$(dirname "$0")/.." && pwd)/ssh.md"

# --- 引数パース ---
while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --gpu) GPU_TYPE="$2"; shift 2 ;;
    *) echo "不明なオプション: $1"; exit 1 ;;
  esac
done

# --- API Key確認 ---
if [ -z "${RUNPOD_API_KEY:-}" ]; then
  source ~/.zshrc 2>/dev/null || true
fi
if [ -z "${RUNPOD_API_KEY:-}" ]; then
  echo "❌ RUNPOD_API_KEY が設定されていません"
  exit 1
fi

echo "============================================"
echo "  並列Pod作成（Volume なし）"
echo "  GPU: $GPU_TYPE"
echo "  Region: ${REGION:-Any}"
echo "============================================"

# --- Step 1: Pod作成 ---
echo ""
echo "[1/5] Pod作成中..."

DATACENTER_ARG=""
if [ -n "$REGION" ]; then
  DATACENTER_ARG=", dataCenterId: \"$REGION\""
fi

RESULT=$(curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"mutation { podFindAndDeployOnDemand(input: { name: \\\"ComfyUI-Parallel\\\", gpuTypeId: \\\"$GPU_TYPE\\\", gpuCount: 1, volumeInGb: 0, containerDiskInGb: 20, imageName: \\\"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04\\\", startSsh: true, ports: \\\"22/tcp,8188/http\\\"${DATACENTER_ARG}, env: [{ key: \\\"HF_TOKEN\\\", value: \\\"{{ RUNPOD_SECRET_HF_TOKEN }}\\\" }] }) { id name desiredStatus } }\"
  }" https://api.runpod.io/graphql)

POD_ID=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['podFindAndDeployOnDemand']['id'])" 2>/dev/null)

if [ -z "$POD_ID" ]; then
  echo "❌ Pod作成に失敗しました"
  echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
  exit 1
fi

echo "  Pod ID: $POD_ID"

# --- Step 2: SSH接続情報を待つ ---
echo ""
echo "[2/5] Pod起動を待機中..."

SSH_IP=""
SSH_PORT=""
for i in $(seq 1 30); do
  sleep 10
  INFO=$(curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"query\": \"{ pod(input: { podId: \\\"$POD_ID\\\" }) { id desiredStatus runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort type } } } }\"
    }" https://api.runpod.io/graphql)

  # runtimeがnullでないか確認
  RUNTIME=$(echo "$INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['pod']['runtime'])" 2>/dev/null)
  if [ "$RUNTIME" = "None" ] || [ -z "$RUNTIME" ]; then
    echo "  待機中... (${i}0秒)"
    continue
  fi

  # SSH接続情報を抽出（TCP, privatePort=22）
  read -r SSH_IP SSH_PORT <<< $(echo "$INFO" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ports = d['data']['pod']['runtime']['ports']
for p in ports:
    if p['privatePort'] == 22 and p['type'] == 'tcp':
        print(p['ip'], p['publicPort'])
        break
" 2>/dev/null)

  if [ -n "$SSH_IP" ] && [ -n "$SSH_PORT" ]; then
    echo "  SSH: root@${SSH_IP} -p ${SSH_PORT}"
    break
  fi
  echo "  待機中... (${i}0秒)"
done

if [ -z "$SSH_IP" ] || [ -z "$SSH_PORT" ]; then
  echo "❌ SSH接続情報の取得に失敗しました（5分タイムアウト）"
  echo "  Pod ID: $POD_ID を手動で確認してください"
  exit 1
fi

# --- Step 3: SSH疎通確認 ---
echo ""
echo "[3/5] SSH接続を確認中..."

SSH_CMD="ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i $SSH_KEY root@${SSH_IP} -p ${SSH_PORT}"

for i in $(seq 1 6); do
  if $SSH_CMD "echo SSH_OK" 2>/dev/null | grep -q "SSH_OK"; then
    echo "  SSH接続OK"
    break
  fi
  if [ "$i" = "6" ]; then
    echo "❌ SSH接続に失敗しました"
    echo "  ssh root@${SSH_IP} -p ${SSH_PORT} -i $SSH_KEY"
    exit 1
  fi
  echo "  リトライ中... (${i}/6)"
  sleep 10
done

# --- Step 4: HF_TOKEN設定 + セットアップ実行 ---
echo ""
echo "[4/5] ComfyUI + Wan 2.1 セットアップ中（約5-10分）..."

# HF_TOKENをSSHセッションに引き継ぐ
$SSH_CMD 'grep -z "HF_TOKEN" /proc/1/environ 2>/dev/null | tr "\0" "\n" >> /root/.bashrc; echo "HF_TOKEN configured"' 2>/dev/null || true

# setup_comfyui.sh をバックグラウンド実行し、完了を待つ
$SSH_CMD "wget -qO /tmp/setup_comfyui.sh ${SETUP_URL} && bash /tmp/setup_comfyui.sh" 2>&1 | while IFS= read -r line; do
  echo "  $line"
done
SETUP_EXIT=${PIPESTATUS[0]}

if [ "$SETUP_EXIT" != "0" ]; then
  echo "⚠️  セットアップがエラーで終了しました（exit code: $SETUP_EXIT）"
  echo "  ログ確認: $SSH_CMD 'tail -30 /workspace/comfyui.log'"
fi

# --- Step 5: ComfyUI起動確認 ---
echo ""
echo "[5/5] ComfyUI起動を確認中..."

HTTP_CODE=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  echo "  ComfyUI: OK (port 8188)"
else
  echo "  ComfyUI: 応答なし（HTTP $HTTP_CODE）"
  echo "  setup_comfyui.shの起動待ちが足りない可能性があります"
  echo "  確認: $SSH_CMD 'tail -30 /workspace/comfyui.log'"
fi

# --- 完了 ---
SSH_CONNECT="ssh root@${SSH_IP} -p ${SSH_PORT} -i ~/.ssh/id_ed25519"

echo ""
echo "============================================"
echo "  ✅ 並列Pod作成完了"
echo "============================================"
echo "  Pod ID:  $POD_ID"
echo "  GPU:     $GPU_TYPE"
echo "  SSH:     $SSH_CONNECT"
echo "  ComfyUI: http://${SSH_IP}:8188"
echo ""
echo "  動画生成コマンド（全シーン渡してロックで自動分配）:"
echo "  python3 scripts/generate_wan_i2v.py \\"
echo "    --host $SSH_IP --port $SSH_PORT \\"
echo "    --prompts scripts/wan_i2v_prompts.json \\"
echo "    --pod-id $POD_ID --terminate &"
echo ""
echo "  ※ Pod1も同じコマンドで並列実行すれば、ロックで自動的にシーンを分配します"
echo "  ※ --terminate: 全シーン完了後にPodを完全削除（Volumeなし用）"
echo "============================================"

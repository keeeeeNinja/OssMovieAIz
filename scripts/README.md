# scripts/ — Pod 並列運用 実行例

複数Pod並列運用（プール方式）の実行例。詳細な仕様は `../CLAUDE.md` の「複数Pod並列運用」章を参照。

```bash
# ── Pod 1（Volume付き）: Flux画像を全シーン生成 ──
python3 scripts/generate_flux_images.py \
  --host $POD1_IP --port $POD1_PORT \
  --prompts scripts/flux_prompts.json \
  --output-root 作業中動画 \
  --lora flux_japanese_girl_v2.safetensors \
  --copy-to-input

# Pod 1 でも Wan を並行実行
python3 scripts/generate_wan_i2v.py \
  --host $POD1_IP --port $POD1_PORT \
  --prompts scripts/wan_i2v_prompts.json \
  --output-root 作業中動画 \
  --pod-id $POD1_ID

# ── Pod 2/3（Wan専用）: Pod作成 → セットアップ(--wan-only) → 画像アップロード → Wan生成 ──
python3 scripts/setup_parallel_pod.py \
  --wan-prompts scripts/wan_i2v_prompts.json \
  --output-root 作業中動画 \
  --generate

# ※ --scenes を省略するとプロンプトJSONの全シーンが対象になる（推奨）
# ※ --flux-prompts は廃止（Pod 1 専用に統一）
# ※ 単一テーマなら従来どおり --output-dir 作業中動画/theme1 を使う
```

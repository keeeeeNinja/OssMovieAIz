# Phase 1 調査結果: RunPod Serverless ComfyUI

調査日: 2026-04-27

## 仕様書からの修正事項（重要）

| 項目 | 仕様書 | 実際 | ソース |
|---|---|---|---|
| 公式イメージ名 | `runpod/ai-worker-comfyui` | **`runpod/worker-comfyui`** | github.com/runpod-workers/worker-comfyui |
| Network Volume マウントパス | `/workspace` | **`/runpod-volume`**（固定、変更不可） | docs.runpod.io |
| カスタムノード Volume 配置 | OK 想定 | **公式が "not suitable for installing custom nodes" と明言** → Custom Dockerfile 必須 | worker-comfyui/docs/customization.md |
| Wan2.1 同梱 | 「公式イメージで対応想定」 | **同梱なし**（base / flux1-schnell / flux1-dev / sdxl / sd3 のみ） | worker-comfyui README |

## 仕様書 TODO 5 項目への回答

### ① カスタムノード対応
- 公式イメージは **base イメージは ComfyUI 本体のみ**。GGUF / KJNodes / VideoHelperSuite は同梱されていない
- 公式推奨は **Custom Dockerfile**:
  ```dockerfile
  FROM runpod/worker-comfyui:5.8.5-base
  RUN comfy-node-install ComfyUI-GGUF ComfyUI-KJNodes ComfyUI-VideoHelperSuite
  ```
- → **当プロジェクトでは自前 Dockerfile が必要**

### ② Flux / Wan2.1 対応
- **Flux**: `flux1-dev` バリアントを継承すれば Flux 本体・テキストエンコーダ・VAE が入る
- **Wan2.1**: 公式同梱なし。Network Volume 上の `/runpod-volume/models/diffusion_models/`, `/runpod-volume/models/vae/` 等に GGUF を置いて参照させる
- LoRA も同様に `/runpod-volume/models/loras/` に配置

### ③ タイムアウト
- 最大 **7 日（604,800 秒）** まで設定可能。デフォルト 600 秒
- → Wan I2V 15 分（900 秒）は余裕で OK

### ④ GPU フォールバック
- **最大 3 GPU タイプをプライオリティ順に指定可能**
- → 既存 RunPod 運用ルール（メモリ: 4090 を 5 分待って在庫切れなら 5090）に合わせて `[RTX 4090, RTX 5090]` を指定する
- ※ メモ: 3090 は使わない（既存ルール）

### ⑤ コールドスタート
- **FlashBoot** が新規エンドポイントでデフォルト有効（スピンダウン後の状態保持）
- 完全排除したいなら **Active Workers ≥ 1**（最低 1 ワーカー常時ウォーム）
- 実測値は Phase 6 で測る

---

## 公式 handler の挙動（自作不要の可能性）

公式 `worker-comfyui` の handler は以下を自動でやる:

- リクエスト `input.workflow`（ComfyUI Export API でエクスポートした JSON）を受け取る
- `input.images`（base64）でアップロード可能
- 内部 ComfyUI の `/prompt` に POST → ポーリング → 完了
- **デフォルトは出力を base64 で返却**、または S3 URL 設定可能

→ **自作 handler は原則不要**。仕様書の「GPU 上では Volume 保存のみ・rclone は GPU 課金外で実行」を満たすには、ワークフロー JSON 側で `SaveImage` / `VHS_VideoCombine` の出力先を `/runpod-volume/outputs/...` に向け、handler レスポンスからは base64 を返さない設定にする（環境変数または公式設定で切替可と想定。Phase 2 で確認）。

→ **Phase 3「handler.py 実装」は大幅縮小**。ワークフロー JSON テンプレート + プレースホルダー機構の設計だけ残す。

---

## 修正後アーキテクチャ

```
┌──────────────────────────────────────────────────────┐
│ Custom Dockerfile (自前ビルド & 公開)                 │
│  FROM runpod/worker-comfyui:5.8.5-base              │
│  RUN comfy-node-install GGUF KJNodes VideoHelper    │
│  → 例: ghcr.io/<user>/ossmovie-comfyui:1.0          │
└──────────────────────────────────────────────────────┘
              ↓ 使用
┌──────────────────────────────────────────────────────┐
│ Serverless Endpoint A (Flux)                         │
│  Image: 上記 Custom Image                            │
│  GPU: [RTX 4090, RTX 5090]  ※ プライオリティ順       │
│  Network Volume: 既存 c1dbeweh5j → /runpod-volume   │
│  Execution Timeout: 600 秒                           │
│  Max Workers: 3, Idle Timeout: 5 秒, FlashBoot ON    │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ Serverless Endpoint B (Wan2.1 I2V)                   │
│  Image: 同上                                          │
│  GPU: [RTX 4090, RTX 5090]                           │
│  Network Volume: 同上                                 │
│  Execution Timeout: 900 秒                           │
└──────────────────────────────────────────────────────┘

Network Volume `/runpod-volume/`
├── models/
│   ├── diffusion_models/    # Wan2.1 GGUF
│   ├── checkpoints/         # Flux dev (公式バリアント由来 or 別配置)
│   ├── loras/               # flux_japanese_girl_v2, Ayano/Rin など
│   ├── vae/
│   └── text_encoders/
├── input/                    # I2V 入力画像
├── workflows/                # ローカルから送る前のテンプレ参照用（任意）
└── outputs/
    ├── images/{job_id}/
    └── videos/{job_id}/
```

---

## 残りの実機確認事項（Phase 2 以降）

これらは Pod を起動しないと正確に分からない:

- [ ] 既存 Network Volume `c1dbeweh5j` のリージョンが Serverless の RTX 4090/5090 在庫が豊富なリージョンか
- [ ] 公式バリアント `flux1-dev` のモデル配置パスが、当プロジェクトの既存 ComfyUI 配置と互換か
- [ ] `comfy-node-install` で当プロジェクトの GGUF / KJNodes / VideoHelperSuite バージョンが入るか
- [ ] 公式 handler の出力モードを「Volume 保存のみ・base64 を返さない」に切り替えられる環境変数があるか
- [ ] コールドスタート実測値（FlashBoot 適用時 vs Active Worker 1 時）

---

## プラン更新方針

承認済みプラン `lively-dazzling-russell.md` に対する変更点:

- **Phase 2 にステップ追加**: Custom Dockerfile 作成と公開（GitHub Container Registry など）
- **Phase 3 大幅縮小**: 自作 handler.py は不要。**ワークフロー JSON テンプレート 2 種**の作成のみに絞る
- **Phase 4 設定値修正**:
  - Image: `runpod/worker-comfyui` → 自前 Custom Image
  - Mount: `/workspace` → `/runpod-volume`
  - GPU フォールバック: 4090 → **5090**（3090 ではない）
- **Phase 5 修正**: 通信先 `https://api.runpod.ai/v2/{endpoint_id}/run`、入力は `input.workflow` キーで JSON を渡す
- **新規ファイル**: `Dockerfile.serverless`、`scripts/build_and_push_image.sh`

## ソース

- [worker-comfyui (GitHub)](https://github.com/runpod-workers/worker-comfyui)
- [Network volumes for Serverless (RunPod Docs)](https://docs.runpod.io/serverless/storage/network-volumes)
- [Endpoint Configurations (RunPod Docs)](https://docs.runpod.io/serverless/endpoints/endpoint-configurations)
- [worker-comfyui Customization Guide](https://github.com/runpod-workers/worker-comfyui/blob/main/docs/customization.md)

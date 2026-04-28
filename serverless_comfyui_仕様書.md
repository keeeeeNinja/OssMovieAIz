# RunPod Serverless ComfyUI 静止画・動画生成システム 仕様書

最終更新: 2026-04-27（v2 — 初回実装フィードバックを反映）

## 1. 概要

RunPod Serverless 上で ComfyUI を動作させ、静止画生成（Flux）と I2V 動画生成（Wan2.1）を行う。Pod ではなく Serverless を使うことで、リクエスト時のみ GPU が起動し、待機中の課金をゼロにする。

静止画と I2V は別エンドポイントとし、静止画を目視確認して OK が出てから I2V に進むワークフローとする。

**handler は公式 `runpod/worker-comfyui` 同梱のものをそのまま使う**（自作不要）。本仕様で作るのは「Custom Dockerfile（カスタムノード焼き込み）+ ワークフロー JSON テンプレ + ローカル投入/取得スクリプト」。

LoRA は本仕様の範囲外（必要になったら別途拡張）。

### 本仕様のスコープ（最終ゴール）

**ローカルからスクリプトを叩けば、Serverless ワーカーが起動して ComfyUI 上でワークフローが走り出すところまで**を完成とする。具体的には:

1. `create_serverless_endpoint.py` で Endpoint A/B が作成できる
2. `serverless_request.py` で job が `IN_QUEUE` → `IN_PROGRESS` に遷移する
3. ワーカーが Custom Image を pull してきて、Volume をマウントし、ComfyUI が起動してワークフロー実行を開始する
4. `serverless_fetch.py` で Volume にアクセスできる（S3 認証が通る）

**ワークフローが最後まで完走して PNG / MP4 が生成されるか**は、ここまで完成させた後の **調整フェーズ**で詰める（モデルパス・ノード互換性・出力先指定等は走らせながら直す）。仕様書は「インフラ起動の正しさ」までを保証する。

---

## 2. インフラ構成

| 項目 | 値 | 備考 |
|---|---|---|
| 計算リソース | RunPod Serverless（GPU: RTX 4090 / 5090 フォールバック） | 3090 は使わない |
| ベースイメージ | **`runpod/worker-comfyui:5.8.5-base`**（公式・base バリアント） | flux/sdxl/sd3 同梱バリアントは使わない（モデルは Volume に置くため） |
| 配布イメージ | `ghcr.io/<owner>/ossmovie-comfyui:latest`（Custom Dockerfile でビルド） | GHA で push 時に自動ビルド |
| ストレージ | RunPod Network Volume `c1dbeweh5j`（EU-RO-1） | 既存の Pod 運用と共用 |
| マウントパス | **`/runpod-volume`**（Serverless 固定、変更不可） | Pod の `/workspace` とは別パス |
| handler | 公式 worker-comfyui 同梱（自作しない） | リクエストの `input.workflow` に ComfyUI ワークフロー JSON を載せれば動く |
| 並列処理 | `workersMax` 設定で台数制御（既定 3） | scalerType=QUEUE_DELAY, scalerValue=4 |

### カスタムノード追加方法

公式 worker-comfyui のドキュメントが「Network Volume はカスタムノードに **not suitable**」と明記しているため、**Custom Dockerfile に焼き込むのが必須**。本プロジェクトで必要なノード:

- `city96/ComfyUI-GGUF`（Wan2.1 GGUF 読み込み）
- `kijai/ComfyUI-KJNodes`（GGUFLoaderKJ / WanVideoTeaCacheKJ / SageAttention 等）
- `Kosinkadink/ComfyUI-VideoHelperSuite`（CreateVideo / SaveVideo）

---

## 3. エンドポイント構成

### エンドポイント A: 静止画生成（Flux）

| 設定項目 | 値 |
|---|---|
| Image | Custom（GHCR） |
| GPU | `["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090"]`（プライオリティ順） |
| Network Volume | `c1dbeweh5j` を `/runpod-volume` にマウント |
| dataCenterIds | `["EU-RO-1"]`（Volume と一致） |
| executionTimeoutMs | 600,000（10 分） |
| workersMin / Max | 0 / 3 |
| idleTimeout | 5 秒 |
| flashboot | true |

### エンドポイント B: I2V 動画生成（Wan2.1）

A と同じだが `executionTimeoutMs: 900,000`（15 分、Wan は 6〜10 分かかる）。

---

## 4. Network Volume `c1dbeweh5j` の既存内容

2026-04-27 Pod 調査で確認済み。**追加の DL は不要**で、現状のまま Serverless から参照できる（ただし extra_model_paths.yaml が必要、Section 5 参照）。

```
/workspace/ComfyUI/                      # Serverless では /runpod-volume/ComfyUI/
├── custom_nodes/                        # ※ Volume 経由で読ませない（Dockerfile 焼き込みに統一）
│   ├── ComfyUI-GGUF
│   ├── ComfyUI-KJNodes
│   ├── ComfyUI-LivePortraitKJ           # 本仕様では不要
│   ├── ComfyUI-Manager                  # Serverless では使わない
│   ├── ComfyUI-VideoHelperSuite
│   ├── ComfyUI_SLK_joy_caption_two      # 本仕様では不要
│   └── WWAA-CustomNodes                 # 本仕様では不要
└── models/
    ├── unet/
    │   ├── flux1-dev.safetensors                    # Flux 本体（fp8）
    │   ├── flux1-kontext-dev-Q8_0.gguf              # 本仕様では未使用
    │   └── wan2.1-i2v-14b-480p-Q5_K_M.gguf          # Wan 本体
    ├── diffusion_models/                            # 空（プレースホルダのみ）
    ├── checkpoints/                                 # SDXL（本仕様では未使用）
    │   ├── sd_xl_base_1.0.safetensors
    │   └── sd_xl_refiner_1.0.safetensors
    ├── clip/
    │   ├── clip_l.safetensors                       # Flux 用 CLIP-L
    │   └── t5xxl_fp8_e4m3fn.safetensors             # Flux 用 T5XXL
    ├── text_encoders/
    │   ├── clip_l.safetensors                       # 重複（旧 clip/ から移行途上）
    │   └── umt5_xxl_fp8_e4m3fn_scaled.safetensors   # Wan 用
    ├── clip_vision/
    │   └── clip_vision_h.safetensors                # Wan 用
    └── vae/
        ├── ae.safetensors                           # Flux 用（gated／HF_TOKEN 必要）
        ├── sdxl_vae.safetensors                     # 本仕様では未使用
        └── wan_2.1_vae.safetensors                  # Wan 用
```

### モデルパス命名規則の注意

- ComfyUI v4 までは `models/clip/`、v5+ から `models/text_encoders/` にリネームされた
- 当 Volume は両方併存（Flux 用 t5xxl は `clip/` のみ、Wan 用 umt5 は `text_encoders/` のみ）
- 公式 worker-comfyui の ComfyUI は v5+ で `text_encoders/` を見るため、`extra_model_paths.yaml` で **両方をリスト**する必要あり（Section 5）

### gated モデル（`ae.safetensors`）

- BFL（Black Forest Labs）の Flux.1-dev VAE は HuggingFace で gated。`HF_TOKEN` がないと wget が 0 バイトファイルを作る
- Volume 上の `ae.safetensors` のサイズを目視で確認（正常は約 330 MB）

---

## 5. ワークフロー設計と出力先制御

### ワークフロー JSON

ローカルリポジトリの `scripts/serverless_workflows/` にプレースホルダ入りテンプレを置く:

- `flux.json` — Flux 静止画
- `wan_i2v.json` — Wan2.1 I2V 動画

ローカル投入スクリプトがプレースホルダを置換して `input.workflow` キーで POST。

### 出力先を Volume に向ける

公式 worker-comfyui のデフォルトは ComfyUI 既定 `output/` フォルダに保存し、handler が base64 で返却する。**GPU 課金中に base64 を ローカル送信するのは無駄**なので、Volume に直書きさせる:

**方法 1: ワークフローの SaveImage / SaveVideo の `filename_prefix` を Volume 絶対パスにする**
```json
"filename_prefix": "/runpod-volume/outputs/images/[JOB_ID]/flux_[SCENE_ID]"
```

**方法 2: Custom Dockerfile の起動引数で `--output-directory /runpod-volume/outputs/` を指定**

方法 1 がシンプル。実装はテンプレ JSON 側で完結する。

### `extra_model_paths.yaml`（Custom Image に同梱）

`base_path` と multi-path 形式で、新旧フォルダ名と `unet/` `diffusion_models/` の両方を見させる。

```yaml
ossmovie:
  base_path: /runpod-volume/ComfyUI/

  unet: |
    models/unet/
    models/diffusion_models/
  diffusion_models: |
    models/unet/
    models/diffusion_models/
  clip: |
    models/text_encoders/
    models/clip/
  text_encoders: |
    models/text_encoders/
    models/clip/
  clip_vision: models/clip_vision/
  vae: models/vae/
  checkpoints: models/checkpoints/
```

---

## 6. ファイル転送方針

GPU 上では Volume への保存のみ行い、ローカルへは **RunPod の S3 互換 API** で取得する（`rclone` ではなく `boto3` / `aws cli`）。

### S3 互換 API のパラメータ

| 項目 | 値 |
|---|---|
| エンドポイント URL | `https://s3api-eu-ro-1.runpod.io`（Volume の DC ごとに変わる） |
| region | **大文字** `EU-RO-1`（小文字にすると SignatureDoesNotMatch） |
| bucket | **Network Volume ID**（`c1dbeweh5j`） |
| signature_version | `s3v4`（boto3 の既定） |
| addressing_style | デフォルト（path 強制不要） |

### よくある詰まり

- 既存の `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 環境変数が残っていると boto3 がそちらを優先する → `unset` してから実行
- region を小文字にすると SigV4 署名が一致せず `SignatureDoesNotMatch` になる
- 認証エラーが出たら、まず RunPod ダッシュボードで S3 キーを **再発行**して試す

---

## 7. handler の方針

公式 `runpod/worker-comfyui` 同梱の handler.py をそのまま使う。要件は以下:

- 自作不要
- リクエストは `{"input": {"workflow": <ComfyUI workflow JSON>, "images": [optional base64 images]}}` 形式
- handler が ComfyUI ローカル API (127.0.0.1:8188) に POST → 完了をポーリング → 結果を返す
- 出力先は Section 5 のとおり、ワークフロー JSON 側で Volume 絶対パスを指定

---

## 8. ローカル側スクリプトの要件

### `scripts/serverless_request.py`（投入）

- `--endpoint flux|i2v` で送信先を切替（環境変数 `RUNPOD_ENDPOINT_{FLUX,I2V}`）
- プロンプト JSON を読み、テンプレートをロード、プレースホルダ置換、`https://api.runpod.ai/v2/{endpoint_id}/run` に POST
- 返却 `id` でポーリング（`/v2/{endpoint_id}/status/{id}`）
- 並列実行のため `fcntl` ロックで未着手シーンを取り合う
- シーン ID `T{N}_C{NN}` から `theme{N}/` ディレクトリへ自動ルーティング
- 完了 job を `job_map_{flux,i2v}.json` に追記（fetch スクリプトが参照）

### `scripts/serverless_fetch.py`（取得）

- boto3 で Volume から `outputs/{images,videos}/{job_id}/` を `作業中動画/theme{N}/` にダウンロード
- `job_map_{flux,i2v}.json` から取得対象を決定
- 単発取得用に `--job-id` `--remote-prefix` `--dest` も用意

### `scripts/create_serverless_endpoint.py`（初回セットアップ）

- RunPod **REST API** (`/v1/templates`, `/v1/endpoints`) で 2 つの Endpoint を作成
- ※ GraphQL `saveTemplate/saveEndpoint` は 403 を返すため REST に限定する
- Template の `env` は dict 形式、Endpoint の `gpuTypeIds` / `dataCenterIds` は配列

---

## 9. 準備フェーズ 1: Volume 内容の確認（Pod 短時間）

**所要 5 分・コスト ~$0.10**。Section 4 の Volume 構造と一致しているか確認するだけ。

1. `/runpod-start` で RTX 4090 Pod を起動（Volume `c1dbeweh5j` を `/workspace` にマウント）
2. SSH で `ls -lh /workspace/ComfyUI/models/{unet,clip,text_encoders,vae,clip_vision}/` を実行
3. **特に `ae.safetensors` のサイズが ~330 MB あるか確認**（0 バイトなら HF_TOKEN 認証失敗で再 DL 必要）
4. Pod 削除

※ Pod 上で Custom Dockerfile を `docker build` することはできない（Pod に Docker daemon が無い）。動作検証は Serverless 上で行う（準備フェーズ 3）。

---

## 10. 準備フェーズ 2: Custom Image 構築

1. `docker/Dockerfile.serverless` を `runpod/worker-comfyui:5.8.5-base` ベースで作成
   - GGUF / KJNodes / VideoHelperSuite を `git clone` + `pip install -r requirements.txt`
   - `docker/extra_model_paths.yaml` を `/comfyui/extra_model_paths.yaml` に COPY
2. `.github/workflows/build-serverless-image.yml` で master push 時に GHA がビルド → GHCR (`ghcr.io/<owner>/ossmovie-comfyui:latest`) に push
3. **GHCR を Public に切替**（GitHub Packages 設定 → Change visibility → Public）。Private のままだと RunPod が pull できない（or `containerRegistryAuthId` を別途登録）

---

## 11. 準備フェーズ 3: Serverless 起動確認（仕様書のゴール）

スコープ（Section 1）のとおり、ここでの**完了基準は「ワーカーが立ち上がって ComfyUI がワークフロー実行を開始した」までを確認する**こと。生成が成功するかは後の調整フェーズで詰める。

### Step 11-1: Endpoint A/B を作成

```bash
python3 scripts/create_serverless_endpoint.py \
  --image ghcr.io/<owner>/ossmovie-comfyui:latest \
  --kind both
```

返却される 2 つの Endpoint ID を環境変数に設定（Section 13）。

**完了基準**: `RUNPOD_ENDPOINT_FLUX` と `RUNPOD_ENDPOINT_I2V` がセットされ、RunPod ダッシュボードに 2 つの Endpoint が表示される。

### Step 11-2: リクエスト疎通確認

Flux 側で `T1_C01` 1 つだけ投入:

```bash
python3 scripts/serverless_request.py --endpoint flux --scenes T1_C01 ...
```

**完了基準**:
- `submit_job` が job_id を返す（HTTP 200）
- ステータスが `IN_QUEUE` → `IN_PROGRESS` に遷移する（= ワーカーが起動して Image を pull・Volume をマウント・ComfyUI が起動した証拠）
- I2V 側でも同様に 1 投入してステータス遷移を確認

ステータスが `FAILED` で返ってきても **インフラ的にはここで OK**。エラー内容（モデルパス・ノード互換性等）は調整フェーズの入口に記録するだけ。

### Step 11-3: S3 取得疎通確認

```bash
python3 scripts/serverless_fetch.py --endpoint flux ...
# あるいは単独で
python3 scripts/list_volume.py ComfyUI/models/
```

**完了基準**: SignatureDoesNotMatch 等の認証エラーが出ず、Volume の中身が listing できる。

### ここまでで仕様書のゴール達成

3 ステップ全部通れば「ローカルからスクリプトで Serverless を起動できる」状態。次は調整フェーズ。

---

## 12. 調整フェーズ（仕様書スコープ外）

Step 11 完了後、生成を実用化するために走らせながら調整する項目を **メモとして** 残す（仕様書では完成義務を負わない）:

- `extra_model_paths.yaml` のキー名 / multi-path 化（Flux / Wan の各モデルが見つかるよう調整）
- ワークフロー JSON のノード名 / モデルファイル名がワーカー上の ComfyUI / カスタムノードバージョンと一致しているか
- ae.safetensors（gated）のサイズ確認・必要なら HF_TOKEN で再 DL
- 出力先（filename_prefix を `/runpod-volume/outputs/...` 絶対パスにするか、Dockerfile の起動引数で `--output-directory` 上書き）
- I2V 用入力画像を Volume の `ComfyUI/input/` にどう置くか（S3 アップロード or ワークフロー側で base64 渡し）
- コールドスタート時間と `delayTime` の実測 → `workersMin` チューニング

---

## 13. 環境変数一覧

`~/.zshrc` に永続化する。シークレット系は手動で追記、非シークレット系は Claude が直接 append しても OK（feedback メモリ参照）。

| 変数 | 機密度 | 例 / 取得元 |
|---|---|---|
| `RUNPOD_API_KEY` | **シークレット** | RunPod ダッシュボード → Settings → API Keys |
| `RUNPOD_S3_ENDPOINT` | 非シークレット | `https://s3api-eu-ro-1.runpod.io` |
| `RUNPOD_S3_ACCESS_KEY` | **シークレット** | Volume → S3 API Settings → Generate |
| `RUNPOD_S3_SECRET_KEY` | **シークレット** | 同上 |
| `RUNPOD_S3_REGION` | 非シークレット | `EU-RO-1`（**大文字**） |
| `RUNPOD_VOLUME_ID` | 非シークレット | `c1dbeweh5j` |
| `RUNPOD_ENDPOINT_FLUX` | 非シークレット | Step 11-1 で取得 |
| `RUNPOD_ENDPOINT_I2V` | 非シークレット | Step 11-1 で取得 |
| `HF_TOKEN` | **シークレット** | gated モデル DL 時のみ。RunPod Secret 経由で渡す |

---

## 14. 料金

- **GPU 課金**: 動画 / 画像を生成している秒数に対してのみ発生（待機 0 円）
- **ストレージ課金**: Network Volume のデータ保持量に応じて月額発生
- **GHCR ストレージ**: 公開イメージは無料、private は GitHub プランに準ずる
- ローカル取得（S3 API）は転送量課金あり（小規模なので無視できる）

---

## 15. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `clip_name1: 't5xxl_fp8_e4m3fn.safetensors' not in [...]` | extra_model_paths.yaml が `models/clip/` を見ていない | yaml の `clip` / `text_encoders` を multi-path 化（Section 5 参照） |
| `Model in folder 'vae' with filename 'ae.safetensors' not found` | Volume 上の ae.safetensors が 0 バイトまたは欠損 | Volume を S3 で list してサイズ確認、必要なら HF_TOKEN 設定して再 DL |
| `SignatureDoesNotMatch` | region が小文字 / `AWS_ACCESS_KEY_ID` 残骸 / キー誤り | region を `EU-RO-1` に直す、`unset AWS_*`、最終手段で S3 キー再発行 |
| GHA `comfy-node-install` で失敗 | base イメージにコマンド未収録 | Dockerfile を `git clone` + `pip install` 方式に切替 |
| Endpoint 作成 GraphQL 403 | API Key 権限 / GraphQL deprecated | REST API (`/v1/templates`, `/v1/endpoints`) を使う |
| Job が長時間 IN_QUEUE | GPU 在庫切れ | gpuTypeIds に 5090 を追加 / 別 DC を試す |
| `dquote>` でターミナルが詰まる | python3 -c の複数行ペーストで `"` が壊れた | `Ctrl+C` で抜けて、スクリプトファイルに書き出してから実行 |

---

## 16. 確認事項（Phase 1 で完了）

| 項目 | 結論 |
|---|---|
| カスタムノード一覧確認 | 公式は何も同梱しない → Custom Dockerfile に焼き込み |
| 公式イメージ Wan2.1 対応 | **同梱なし**（base / flux1-* / sdxl / sd3 のみ）。Wan は Volume + GGUF カスタムノードで対応 |
| タイムアウト上限 | 最大 7 日（604,800 秒）、Wan の 15 分は余裕 |
| GPU 在庫フォールバック | `gpuTypeIds` に最大 3 つプライオリティ順で指定 |
| コールドスタート時間 | FlashBoot 有効。実測は Step 11 で計測 |
| Network Volume Serverless マウント | OK、ただし `/runpod-volume` 固定。Pod の `/workspace` とは別パス |

---

## 17. 変更履歴

- v1 (2026-04-27 初版): 基本仕様
- v2 (2026-04-27 改訂): 初回実装フィードバック反映
  - イメージ名修正 (`runpod/worker-comfyui`)
  - マウントパス修正 (`/runpod-volume`)
  - カスタムノードは Custom Dockerfile 必須を明記
  - handler は公式流用に変更
  - rclone → S3 互換 API (boto3) に変更
  - Volume の現状を Section 4 に追記
  - 検証フェーズを 3 段階に分割
  - 環境変数一覧 / トラブルシューティングセクション新設
  - LoRA は範囲外として除外
- v2.1 (2026-04-27): スコープ縮小
  - 最終ゴールを「スクリプトで Serverless ワーカー起動・ComfyUI 実行開始まで」に変更
  - 生成完走は Section 12「調整フェーズ」として仕様書スコープ外に移動

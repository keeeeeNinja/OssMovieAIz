# RunPod Serverless ComfyUI 導入手順

仕様書 `serverless_comfyui_仕様書.md` と Phase 1 調査結果 `serverless_調査結果.md` を踏まえた実行手順。

---

## 0. 前提

- RunPod アカウント、`RUNPOD_API_KEY`（既存）
- GitHub アカウント `keeeeeNinja`（GitHub Container Registry を利用）
- 既存 Network Volume `c1dbeweh5j`（EU-RO-1、モデル一式入り）

---

## 1. リポジトリにファイルをコミット & push

すでに作成済みのファイル群:

- `docker/Dockerfile.serverless` — Custom image
- `docker/extra_model_paths.yaml` — Volume 上のモデルパス定義
- `.github/workflows/build-serverless-image.yml` — GHA で GHCR に自動 push
- `scripts/serverless_workflows/{flux,flux_lora,wan_i2v}.json` — ワークフロー JSON テンプレ
- `scripts/serverless_request.py` — Serverless API へのリクエスト送信
- `scripts/serverless_fetch.py` — S3 互換 API で Volume からファイル取得
- `scripts/create_serverless_endpoint.py` — Endpoint 作成

```bash
git add docker/ .github/ scripts/serverless_workflows/ \
        scripts/serverless_request.py scripts/serverless_fetch.py \
        scripts/create_serverless_endpoint.py \
        serverless_調査結果.md serverless_導入手順.md
git commit -m "RunPod Serverless ComfyUI 導入: Dockerfile / GHA / ワークフロー / 投入&取得スクリプト"
git push origin master
```

push を契機に GitHub Actions が動き、`ghcr.io/keeeeeninja/ossmovie-comfyui:latest` がビルド・公開される（5〜10 分）。

### GHCR の公開設定
- 初回 push 後、GitHub の Packages 画面で `ossmovie-comfyui` を **Public** にする（推奨。private なら次の手順で RunPod 側に Container Registry Auth 登録が必要）

---

## 2. RunPod の S3 互換 API キーを発行

1. RunPod ダッシュボード → Storage → Network Volumes → `c1dbeweh5j` → S3 API Settings
2. Access Key / Secret Key を発行
3. データセンターのエンドポイント URL を控える（EU-RO-1 なら `https://s3api-eu-ro-1.runpod.io`）
4. `~/.zshrc` に追記:

```bash
export RUNPOD_S3_ENDPOINT="https://s3api-eu-ro-1.runpod.io"
export RUNPOD_S3_ACCESS_KEY="<access_key>"
export RUNPOD_S3_SECRET_KEY="<secret_key>"
export RUNPOD_S3_REGION="EU-RO-1"
export RUNPOD_VOLUME_ID="c1dbeweh5j"
```

`source ~/.zshrc` で反映。

---

## 3. Endpoint A/B を作成

GHA のビルドが完了してから:

```bash
python3 scripts/create_serverless_endpoint.py \
  --image ghcr.io/keeeeeninja/ossmovie-comfyui:latest \
  --volume-id c1dbeweh5j \
  --datacenter EU-RO-1 \
  --kind both
```

実行末尾に出る Endpoint ID 2 つを `~/.zshrc` に追加:

```bash
export RUNPOD_ENDPOINT_FLUX="<flux_endpoint_id>"
export RUNPOD_ENDPOINT_I2V="<i2v_endpoint_id>"
```

`source ~/.zshrc`。

---

## 4. 1 シーンだけテスト（Flux）

```bash
# 既存の flux_prompts.json のうち T1_C01 だけ
python3 scripts/serverless_request.py \
  --endpoint flux \
  --prompts scripts/flux_prompts.json \
  --output-root 作業中動画 \
  --scenes T1_C01 \
  --lora flux_japanese_girl_v2.safetensors

# Volume から取得
python3 scripts/serverless_fetch.py \
  --endpoint flux \
  --output-root 作業中動画
```

`作業中動画/theme1/flux_T1_C01.png` ができれば OK。実行時間（コールドスタート + 生成）と実行料金を `serverless_調査結果.md` に追記。

問題があれば:
- ジョブが FAILED → `https://api.runpod.ai/v2/<endpoint_id>/status/<job_id>` のエラーログを確認
- カスタムノードが見つからない → Dockerfile.serverless にノードが入っているか確認、再ビルド
- モデルパスが見つからない → `docker/extra_model_paths.yaml` のキー名・パスを実機構造（`unet/` 実体）と突き合わせる

---

## 5. 1 シーンだけテスト（Wan I2V）

Step 4 の Flux 結果（PNG）を Volume の `/runpod-volume/ComfyUI/input/` にアップロードする必要がある。これは現状以下の手段で実施:

**方法 A: S3 API でアップロード**
```bash
aws s3 cp 作業中動画/theme1/flux_T1_C01.png \
  s3://c1dbeweh5j/ComfyUI/input/flux_T1_C01.png \
  --endpoint-url $RUNPOD_S3_ENDPOINT
```
（Phase 1 で SignatureDoesNotMatch エラー報告ありなので、`--region EU-RO-1` 等を試す）

**方法 B: 既存 Pod を踏み台に SCP**（Pod 起動中なら）
```bash
scp -P <port> -i ~/.ssh/id_ed25519 \
  作業中動画/theme1/flux_T1_C01.png \
  root@<ip>:/workspace/ComfyUI/input/
```

その後:
```bash
python3 scripts/serverless_request.py \
  --endpoint i2v \
  --prompts scripts/wan_i2v_prompts.json \
  --output-root 作業中動画 \
  --scenes T1_C01

python3 scripts/serverless_fetch.py \
  --endpoint i2v \
  --output-root 作業中動画
```

`作業中動画/theme1/scene_T1_C01_wan21.mp4` ができれば OK。

---

## 6. 並列 3 シーンでベンチマーク

```bash
python3 scripts/serverless_request.py \
  --endpoint flux \
  --prompts scripts/flux_prompts.json \
  --output-root 作業中動画 \
  --scenes T1_C01,T1_C02,T1_C03 \
  --lora flux_japanese_girl_v2.safetensors
```

Max Workers=3 なので 3 並列で動く。job_map_flux.json の `execution_time_ms` `delay_time_ms` を見て:
- delay_time_ms = コールドスタート + キュー待ち
- execution_time_ms = 実生成時間

これを Pod 運用と比較してコスト評価。

---

## 7. CLAUDE.md / スキル統合

Serverless で動画 1 本が完走したら:

- `CLAUDE.md` の Step 6/7 を Serverless 版に更新
- `.claude/skills/` に `/serverless-flux` `/serverless-i2v` を追加（既存スキルは温存）
- 既存 Pod 運用スクリプト（`setup_comfyui.sh`, `setup_parallel_pod.py`, `generate_flux_images.py`, `generate_wan_i2v.py`）は **当面残す**

---

## トラブルシューティング

| 症状 | 原因候補 | 対処 |
|---|---|---|
| GHA ビルドが `comfy-node-install` で失敗 | base イメージにコマンド未収録 | `Dockerfile.serverless` を `git clone` ベースに修正済み（既に対応済み） |
| Endpoint 作成で `gpuIds` バリデーションエラー | GPU 名フォーマット違い | RunPod ダッシュボードで利用可能な GPU 名を確認 (`runpodctl get gpu`) |
| モデルが見つからない | extra_model_paths.yaml のパス | Pod 上で `ls /workspace/ComfyUI/models/` と Serverless の `/runpod-volume/ComfyUI/models/` を突き合わせる。Volume は同じなので構造は一致するはず |
| S3 SignatureDoesNotMatch | EU-RO-1 で報告例あり | エンドポイント URL のリージョン部分を再確認、`signature_version=s3v4` を確認、Access Key を再発行 |
| 公式 handler の base64 レスポンスがでかい | 動画は数十 MB → API 経路で base64 で送られるとオーバーヘッド大 | ワークフロー側で `SaveVideo` の filename_prefix を `/runpod-volume/outputs/...` 絶対パス指定するか、Custom Dockerfile で `--output-directory /runpod-volume/outputs` を起動引数に追加（Phase 6 で詰める） |

---

## 残タスク（実装が完了次第ユーザーに依頼）

- [ ] git commit & push（GHA をキック）
- [ ] GHA ビルド完了確認
- [ ] GHCR を public にする
- [ ] RunPod S3 認証情報を `~/.zshrc` に追加
- [ ] `create_serverless_endpoint.py` 実行
- [ ] Endpoint ID を `~/.zshrc` に追加
- [ ] 1 シーンテスト（Flux → Wan）
- [ ] 並列 3 シーンでコスト計測
- [ ] 動画 1 本完走したら CLAUDE.md 更新
- [ ] **動作確認後、Pod を停止**（現在 RTX 4090 Pod が起動中）

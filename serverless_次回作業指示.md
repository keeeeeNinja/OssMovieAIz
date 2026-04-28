# RunPod Serverless ComfyUI 次回作業指示書

最終更新: 2026-04-28
前提資料: `serverless_comfyui_仕様書.md` / `serverless_調査結果.md` / `serverless_導入手順.md`

---

## 0. 背景と方針変更

前回までの作業で詰まった点と、それを踏まえた方針変更を以下にまとめる。**この指示書は仕様書 v2.1 を上書きするものではなく、運用方針の追加・修正点として位置づける。**

### 詰まった点
- 環境変数の永続化で `~/.zshrc` ではないコマンド（heredoc 等）を使ってしまい、変数がグローバルに反映されなかった
- やり直し時に提示されたコマンド（`<<EOF` 形式と推測される heredoc）が複雑で完了できなかった
- 結果、手作業が多くなり時間切れ

### 方針変更
1. **環境変数は `~/.zshrc` をやめて `.env` ファイル方式に切り替える**（heredoc も廃止）
2. **Custom Image は Keeeee 自身が管理する Public Image として運用**し、講座視聴者には完成イメージだけ使わせる（GitHub / GHA / Dockerfile を視聴者の作業から完全に消す）
3. **イメージタグは `latest` ではなく固定バージョン（`v1.0.0` 等）を視聴者向けに案内**

---

## 1. 環境変数の `.env` 方式への移行

### 1-1. 既存の `~/.zshrc` から Serverless 系 export 行を削除

`~/.zshrc` を開き、以下のいずれかに該当する行をすべて削除する（コメントアウトでも可）:

- `RUNPOD_S3_ENDPOINT`
- `RUNPOD_S3_ACCESS_KEY`
- `RUNPOD_S3_SECRET_KEY`
- `RUNPOD_S3_REGION`
- `RUNPOD_VOLUME_ID`
- `RUNPOD_ENDPOINT_FLUX`
- `RUNPOD_ENDPOINT_I2V`

**zshrc に残すもの**（Pod 系スキルが Bash から読むため、`.env` に移すと壊れる）:

- `RUNPOD_API_KEY` — `/runpod-start` skill が curl で使う
- `HF_TOKEN` — `setup_comfyui.sh` が gated モデル DL に使う

削除後 `source ~/.zshrc` を実行し、新しいシェルで以下を確認:

- `echo $RUNPOD_S3_ACCESS_KEY` → **空**（Serverless 系は zshrc から消えた）
- `echo $RUNPOD_API_KEY` → **値が出る**（Pod 系は残っている）

**重要**: Serverless 系は `~/.zshrc` と `.env` の両方に書かれていると挙動が予測しづらいので `.env` に一本化する。Pod 系（`RUNPOD_API_KEY` / `HF_TOKEN`）は zshrc 側のままにして役割分担する。

### 1-2. `.env.example` をリポジトリルートに作成

```
# ※ RUNPOD_API_KEY と HF_TOKEN は ~/.zshrc 側で管理する（Section 1-1 参照）
# このファイルには Serverless 専用の環境変数だけを書く

# RunPod 共通
RUNPOD_VOLUME_ID=c1dbeweh5j

# RunPod S3 互換 API（Network Volume アクセス用）
RUNPOD_S3_ENDPOINT=https://s3api-eu-ro-1.runpod.io
RUNPOD_S3_ACCESS_KEY=
RUNPOD_S3_SECRET_KEY=
RUNPOD_S3_REGION=EU-RO-1

# RunPod Serverless Endpoints（Step 6 完了後に追記）
RUNPOD_ENDPOINT_FLUX=
RUNPOD_ENDPOINT_I2V=

# Serverless 用 Custom Image（疎通確認後に v1.0.0 等の固定タグに切り替える）
SERVERLESS_IMAGE=ghcr.io/keeeeeninja/ossmovie-comfyui:latest
```

`.env.example` はコミット対象。値は空でよい。

### 1-3. `.env` を作成（gitignore 対象）

`.env.example` を `.env` にコピーし、実際のキー値を埋める。

```bash
cp .env.example .env
```

`.gitignore` に `.env` が含まれていることを確認する（無ければ追記）。

### 1-4. RunPod S3 API キーを再発行

仕様書 Section 6 より、認証エラー回避のため最終手段としてキー再発行が推奨されている。今回は**最初から再発行する前提で進める**:

1. RunPod ダッシュボード → Storage → Network Volumes → `c1dbeweh5j` → S3 API Settings
2. Access Key / Secret Key を**新規発行**（既存キーは破棄）
3. 発行された値を `.env` の `RUNPOD_S3_ACCESS_KEY` / `RUNPOD_S3_SECRET_KEY` に記入

### 1-5. スクリプトを `python-dotenv` 対応に修正

対象ファイル:
- `scripts/serverless_request.py`
- `scripts/serverless_fetch.py`
- `scripts/create_serverless_endpoint.py`
- （存在すれば）`scripts/list_volume.py`

各ファイルの**冒頭**（import 直後）に以下を追加:

```python
from dotenv import load_dotenv
load_dotenv(override=True)
```

**`override=True` 必須**: デフォルトの `load_dotenv()` は既存の環境変数を**上書きしない**。`~/.zshrc` から削除し損ねた古い値や、過去のセッションで `export` した残骸があると、`.env` の新しい値が無視される事故が起きる。`override=True` で常に `.env` を正とする。

加えて、boto3 を使うスクリプト（`serverless_fetch.py` / `list_volume.py`）では `load_dotenv` 直後に AWS 標準環境変数の残骸を防御的に除去する:

```python
for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(k, None)
```

これで RunPod の S3 キーと AWS のキーが混在しても確実に RunPod 側を使う（Section 1-7 関連）。

`python-dotenv` がインストールされていない場合は `pip install python-dotenv` を実行（`requirements.txt` にも追記）。

### 1-6. 疎通確認

`.env` 設定後、以下で S3 認証が通ることを確認:

```bash
python3 scripts/list_volume.py ComfyUI/models/
```

`SignatureDoesNotMatch` 等が出ず、Volume の中身が listing できれば OK。

**もし `list_volume.py` が未実装なら**、`serverless_fetch.py` に `--list-only` オプションを追加して同等の挙動にしてもよい。仕様書 Section 11-3 の完了基準を満たすこと。

### 1-7. 注意：`AWS_*` 環境変数の干渉

仕様書 Section 6 にある通り、既存の `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` が環境に残っていると boto3 がそちらを優先する。スクリプト実行前に以下を確認:

```bash
env | grep AWS_
```

何か出てきたら `unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY` してから実行する。`.env` 方式に移行することで `~/.zshrc` 由来の干渉は減るが、過去のセッションで export している可能性は残る。

---

## 2. Custom Image の Public Image 運用への切り替え

### 2-1. 運用方針

- **Keeeee がイメージビルドと公開を一括で管理**する
- **講座視聴者には完成イメージのタグ名だけ伝え、Dockerfile / GHA / GHCR の操作を一切させない**
- イメージは **`ghcr.io/keeeeeninja/ossmovie-comfyui:v1.0.0`** のように**固定バージョンタグ**で公開する
- `latest` タグは Keeeee の開発用途のみ。視聴者向けドキュメントには絶対に書かない

### 2-2. Dockerfile の固定バージョン化（推奨、ただし時間がなければ次回以降でも可）

仕様書 Section 15 トラブルシューティング表に従い、`comfy-node-install` ではなく `git clone + pip install` 方式にする。さらに、各カスタムノードを**特定のコミットハッシュまたはリリースタグで固定**する。

対象:
- `city96/ComfyUI-GGUF`
- `kijai/ComfyUI-KJNodes`
- `Kosinkadink/ComfyUI-VideoHelperSuite`

例（`docker/Dockerfile.serverless`）:

```dockerfile
FROM runpod/worker-comfyui:5.8.5-base

WORKDIR /comfyui/custom_nodes

RUN git clone https://github.com/city96/ComfyUI-GGUF.git \
    && cd ComfyUI-GGUF \
    && git checkout <固定ハッシュまたはタグ> \
    && pip install -r requirements.txt

# KJNodes / VideoHelperSuite も同様

COPY docker/extra_model_paths.yaml /comfyui/extra_model_paths.yaml
```

**理由**: `comfy-node-install` や `git clone` のみだと、ビルドのたびに上流の最新版が入る。上流が破壊的変更を入れた瞬間、視聴者の新規エンドポイントが壊れる。固定すれば「Keeeee が検証した時点の動作する組み合わせ」を凍結できる。

**ピン留めタイミング**: コミットハッシュは「**直近で疎通確認できた時点のコミット**」を選ぶ。検証前に古いコミットを固定すると、壊れたバージョンを凍結するリスクがある。Section 4 の作業順序では、**まず `latest` で疎通確認 → 動いた時点のコミットを取得 → 固定 → `v1.0.0` タグ切り**の順とする（chicken-and-egg を避ける）。

**注意**: 今晩作業時間が限られているなら、固定化は別日でよい。その場合 `latest` で運用継続する旨を視聴者向けドキュメントに**書かない**こと（後で固定タグに切り替えるため）。

### 2-3. GHA でのビルドとタグ切り

`.github/workflows/build-serverless-image.yml` を、push 時の `latest` ビルドに加えて **git tag が push された時に同名のイメージタグを発行する** よう拡張する。

挙動:
- `git tag v1.0.0 && git push origin v1.0.0` → `ghcr.io/keeeeeninja/ossmovie-comfyui:v1.0.0` が公開される
- master push → `latest` が更新される（開発用）

### 2-4. GHCR を Public に設定

GitHub の Packages 画面で `ossmovie-comfyui` を **Public** に変更（既に対応済みなら確認のみ）。

### 2-5. 視聴者向けドキュメントの記述

講座視聴者には以下のように案内する想定:

> Endpoint 作成時は以下のイメージ名を指定してください:
> `ghcr.io/keeeeeninja/ossmovie-comfyui:v1.0.0`

つまり `create_serverless_endpoint.py` の `--image` 引数のデフォルト値を `v1.0.0` 固定タグにしておく（または `.env` の `SERVERLESS_IMAGE` 変数で管理）。

---

## 3. Endpoint 作成と疎通確認（仕様書 Step 11 の再実行）

`.env` と Public Image が揃ったら、仕様書 Section 11 の Step 11-1 〜 11-3 を順に実行する。

### 3-1. Endpoint A/B 作成

```bash
python3 scripts/create_serverless_endpoint.py \
  --image ghcr.io/keeeeeninja/ossmovie-comfyui:v1.0.0 \
  --kind both
```

成功したら `RUNPOD_ENDPOINT_FLUX` / `RUNPOD_ENDPOINT_I2V` を `.env` に追記。

### 3-2. リクエスト疎通確認

```bash
python3 scripts/serverless_request.py --endpoint flux --scenes T1_C01 ...
```

完了基準（仕様書 Section 11-2）:
- HTTP 200 で job_id が返る
- ステータスが `IN_QUEUE` → `IN_PROGRESS` に遷移する
- I2V 側でも同様に確認

`FAILED` でもインフラ的には OK（仕様書 Section 11-2 注記参照）。

### 3-3. S3 取得疎通確認

Section 1-6 で済ませている想定。未実施ならここで実行。

---

## 4. 作業順序まとめ（今晩の TODO）

優先度順:

1. **`.env.example` 作成・`.gitignore` 確認・`.env` 作成（中身は空でも先に）**
2. **`~/.zshrc` から Serverless 系 export 削除（`RUNPOD_API_KEY` と `HF_TOKEN` は残す）、新シェルで反映確認**
3. **RunPod S3 API キー再発行 → `.env` に記入**
4. **スクリプト 3 本（+`list_volume`）に `load_dotenv(override=True)` + AWS_* 除去を追加、`requirements.txt` 更新**
5. **S3 疎通確認（`list_volume` で Volume listing できるか）**
6. **Endpoint A/B 作成と疎通確認** — `--image` は当面 `latest` のまま、`IN_QUEUE` → `IN_PROGRESS` 遷移まで確認 ← **仕様書 v2.1 のスコープ完了基準**
7. （余裕があれば）**Dockerfile のカスタムノードを「Step 6 で動作確認できたコミット」でピン留め、`v1.0.0` タグを切って GHA でビルド**
8. （余裕があれば）**`SERVERLESS_IMAGE` の `.env.example` デフォルトと `create_serverless_endpoint.py` の `--image` デフォルトを `v1.0.0` に切り替え**

**1〜6 までを必達タスクとする**（仕様書 v2.1 のスコープを満たすため）。7〜8 は Public Image を視聴者に案内するために必要だが、今晩無理でも次回以降でよい。

---

## 5. やらないこと（明示的に除外）

- `~/.zshrc` への heredoc / `cat <<EOF` での書き込み（前回詰まった原因）
- 視聴者に Dockerfile / GHA / GHCR 操作をさせる前提の設計
- `latest` タグを視聴者向けドキュメントに記載すること
- LoRA 関連の追加実装（仕様書 Section 1 で範囲外と明記）

---

## 6. 完了確認チェックリスト

作業完了時に以下を Keeeee と一緒に確認:

- [ ] `.env.example` がリポジトリにコミットされている
- [ ] `.env` が `.gitignore` に含まれており、ローカルで値が埋まっている
- [ ] `~/.zshrc` から Serverless 系 export 行が削除されている（`RUNPOD_API_KEY` / `HF_TOKEN` は残す）
- [ ] 新規シェルで `echo $RUNPOD_S3_ACCESS_KEY` が空、`echo $RUNPOD_API_KEY` は値が出る（切り分け確認）
- [ ] `env | grep AWS_` が空（過去セッションの AWS_* 残骸なし）
- [ ] スクリプト 3 本が `load_dotenv(override=True)` + `AWS_*` 除去で `.env` を読み込めている
- [ ] `requirements.txt` に `python-dotenv` が含まれている
- [ ] `list_volume` 系コマンドで Volume の中身が listing できる
- [ ] **Endpoint A/B が作成され、`.env` に ID が記入されている**（必達）
- [ ] **Endpoint A への 1 ジョブ投入で `IN_QUEUE` → `IN_PROGRESS` まで遷移を確認**（仕様書 v2.1 スコープ完了基準・必達）
- [ ] （実施した場合）Dockerfile が「Step 6 で動作確認したコミット」でピン留めされ、`v1.0.0` タグが GHCR に存在する
- [ ] （実施した場合）`SERVERLESS_IMAGE` のデフォルトが `v1.0.0` に切り替わっている

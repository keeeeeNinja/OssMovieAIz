---
name: runpod-start
description: （非推奨・例外用途のみ）RunPod APIでPodを立ち上げ、SSH接続確認、setup_comfyui.sh実行、ssh.md更新まで一気通貫で行う。通常の動画制作フローは Serverless（`/flux-image` `/wan-video`）に移行済み。「Pod立ち上げて」「LoRA学習用に5090で起動」など Pod が必要な例外用途のみで使う。
allowed-tools: Bash, Read, Write, Edit
---

## RunPod Pod 起動スキル（非推奨）

> ⚠️ **通常の動画制作フローでは使わない。** Flux/Wan I2V は RunPod Serverless（`scripts/serverless_request.py`）に移行済み。このスキルは LoRA 学習・新規モデルの動作確認・カスタムノード検証など、永続 Pod が必要な例外用途のみで起動する。

RunPod GraphQL APIを使ってPodを作成し、ComfyUIが使える状態にするまで自動化する。

---

### 前提条件

- 環境変数 `RUNPOD_API_KEY` が設定済み（~/.zshrc）
- SSH鍵 `~/.ssh/id_ed25519` がRunPodに登録済み

---

### GPUモード判定

ユーザーの指示から使用するGPUを判定する:

| ユーザーの指示 | GPUモード | Dockerイメージ | setup_comfyui.shフラグ |
|---|---|---|---|
| 「Pod起動して」（デフォルト） | RTX 4090 | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` | `--restart` |
| 「5090で起動して」 | RTX 5090 | `runpod/pytorch:2.8.0-py3.12-cuda12.8.1-devel-ubuntu22.04` | `--restart --5090` |

---

### 実行手順

#### Step 1: Pod作成

**RTX 4090モード（デフォルト）:**

```bash
source ~/.zshrc && curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { podFindAndDeployOnDemand(input: { name: \"ComfyUI-4090\", gpuTypeId: \"NVIDIA GeForce RTX 4090\", gpuCount: 1, volumeInGb: 0, containerDiskInGb: 80, networkVolumeId: \"c1dbeweh5j\", volumeMountPath: \"/workspace\", imageName: \"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04\", startSsh: true, ports: \"22/tcp,8188/http\", dataCenterId: \"EU-RO-1\", env: [{ key: \"HF_TOKEN\", value: \"{{ RUNPOD_SECRET_HF_TOKEN }}\" }] }) { id name desiredStatus } }"
  }' https://api.runpod.io/graphql
```

**RTX 5090モード:**

```bash
source ~/.zshrc && curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { podFindAndDeployOnDemand(input: { name: \"ComfyUI-5090\", gpuTypeId: \"NVIDIA GeForce RTX 5090\", gpuCount: 1, volumeInGb: 0, containerDiskInGb: 80, networkVolumeId: \"c1dbeweh5j\", volumeMountPath: \"/workspace\", imageName: \"runpod/pytorch:2.8.0-py3.12-cuda12.8.1-devel-ubuntu22.04\", startSsh: true, ports: \"22/tcp,8188/http\", dataCenterId: \"EU-RO-1\", env: [{ key: \"HF_TOKEN\", value: \"{{ RUNPOD_SECRET_HF_TOKEN }}\" }] }) { id name desiredStatus } }"
  }' https://api.runpod.io/graphql
```

**GPU フォールバック戦略:**

1. 指定されたGPUで作成を試す
2. 在庫切れなら **30秒間隔で最大5分リトライ**
3. 4090モードで5分待っても取れなければ **5090にフォールバック**（setup_comfyui.shは `--restart --5090` に切り替え、Dockerイメージも5090用に変更）
4. 5090モードで取れなければユーザーに報告して停止

**デフォルト設定:**
- GPU: ユーザー指示による（デフォルト4090）
- リージョン: EU-RO-1
- Network Volume: `c1dbeweh5j`（100GB、/workspace マウント）
- ポート: 22/tcp（SSH）、8188/http（ComfyUI）
- 環境変数: HF_TOKEN（RunPodシークレット参照）

ユーザーが別のGPUやリージョンを明示指定した場合は、フォールバックせずその設定のままで作成する。

#### Step 2: 起動待ち＋SSH接続情報取得

45秒待ってからポーリング。`runtime` が null でなくなるまで待つ。

```bash
source ~/.zshrc && curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ pod(input: { podId: \"<POD_ID>\" }) { id desiredStatus runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort type } } } }"
  }' https://api.runpod.io/graphql
```

レスポンスから **TCP type, privatePort=22** のエントリを探す:
- `ip` → SSH接続先IP
- `publicPort` → SSHポート番号

#### Step 3: SSH接続テスト

```bash
ssh -T root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no 'echo SSH_OK'
```

#### Step 4: 環境変数をSSHセッションに引き継ぐ

RunPodの環境変数はコンテナのinit processにはあるが、SSHセッションには渡らない。
`/proc/1/environ` から読み込んで `/root/.bashrc` に書き出す:

```bash
ssh -T root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no \
  'grep -z "HF_TOKEN" /proc/1/environ | tr "\0" "\n" >> /root/.bashrc && echo "HF_TOKEN exported"'
```

#### Step 5: setup_comfyui.sh 実行

Network Volume付きなので `--restart` モード（pip依存再インストール + ComfyUI起動）。
5090モードの場合は `--5090` フラグを追加する。

**4090の場合:**
```bash
ssh -T root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no \
  'wget -qO- https://raw.githubusercontent.com/keeeeeNinja/OssMovieAIz/master/setup_comfyui.sh | bash -s -- --restart'
```

**5090の場合:**
```bash
ssh -T root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no \
  'wget -qO- https://raw.githubusercontent.com/keeeeeNinja/OssMovieAIz/master/setup_comfyui.sh | bash -s -- --restart --5090'
```

**タイムアウト: 300秒**（5090はPyTorch nightlyインストールに時間がかかる場合あり）

#### Step 6: ssh.md 更新

`ssh.md` を新しいSSH接続コマンドで上書き:

```
ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519
```

#### Step 7: 完了報告

以下をユーザーに報告:
- Pod ID
- GPU
- SSH接続コマンド
- ComfyUIステータス
- HF_TOKEN設定状況

---

### Volume なしPod（並列運用時）

ユーザーが「Volumeなしで」「2台目」と指定した場合:
- `networkVolumeId` と `volumeMountPath` を削除
- Step 5 で `--restart` ではなくフルセットアップ（引数なし）を実行
- タイムアウト: 600秒（モデルDL含む）

---

### トラブルシューティング

| 問題 | 原因 | 対処 |
|------|------|------|
| `Permission denied (publickey)` | SSH鍵不一致 | `myself { pubKey }` で確認、`updateUserSettings` で更新 |
| `invalid mount config` | volumeMountPath未指定 | `/workspace` を指定 |
| HF_TOKEN が空 | SSHセッションに環境変数が渡らない | `/proc/1/environ` から読み込む（Step 4） |
| EU-RO-1にGPUがない | 在庫切れ | `dataCenterId` を削除してAny regionにする |
| GPUが取れない | 全リージョン在庫切れ | ユーザーに報告して停止 |
| 5090で「CUDA error: no kernel image」 | PyTorch/CUDAバージョン不一致 | setup_comfyui.shに `--5090` を渡しているか確認。Dockerイメージが `cuda12.8` 以上であること |

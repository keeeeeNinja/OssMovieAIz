---
name: runpod-start
description: RunPod APIでRTX 4090 Podを立ち上げ、SSH接続確認、setup_comfyui.sh実行、ssh.md更新まで一気通貫で行う。「Pod立ち上げて」「RunPod起動」「Pod起動して」という場面で必ず使う。
allowed-tools: Bash, Read, Write, Edit
---

## RunPod Pod 起動スキル

RunPod GraphQL APIを使ってPodを作成し、ComfyUIが使える状態にするまで自動化する。

---

### 前提条件

- 環境変数 `RUNPOD_API_KEY` が設定済み（~/.zshrc）
- SSH鍵 `~/.ssh/id_ed25519` がRunPodに登録済み

---

### 実行手順

#### Step 1: Pod作成

```bash
source ~/.zshrc && curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { podFindAndDeployOnDemand(input: { name: \"ComfyUI-4090\", gpuTypeId: \"NVIDIA GeForce RTX 4090\", gpuCount: 1, volumeInGb: 0, containerDiskInGb: 20, networkVolumeId: \"c1dbeweh5j\", volumeMountPath: \"/workspace\", imageName: \"runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04\", startSsh: true, ports: \"22/tcp,8188/http\", dataCenterId: \"EU-RO-1\", env: [{ key: \"HF_TOKEN\", value: \"{{ RUNPOD_SECRET_HF_TOKEN }}\" }] }) { id name desiredStatus } }"
  }' https://api.runpod.io/graphql
```

**デフォルト設定:**
- GPU: RTX 4090
- リージョン: EU-RO-1
- Network Volume: `c1dbeweh5j`（100GB、/workspace マウント）
- ポート: 22/tcp（SSH）、8188/http（ComfyUI）
- 環境変数: HF_TOKEN（RunPodシークレット参照）

ユーザーが別のGPUやリージョンを指定した場合はパラメータを変更する。

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

#### Step 5: setup_comfyui.sh --restart 実行

Network Volume付きなので `--restart` モード（pip依存再インストール + ComfyUI起動）:

```bash
ssh -T root@<IP> -p <PORT> -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no \
  'wget -qO- https://raw.githubusercontent.com/keeeeeNinja/OssMovieAIz/master/setup_comfyui.sh | bash -s -- --restart'
```

**タイムアウト: 180秒**（pip install + ComfyUI起動 + ヘルスチェック待ち）

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

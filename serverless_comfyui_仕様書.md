# RunPod Serverless ComfyUI 静止画・動画生成システム 仕様書

最終更新: 2026-04-27

## 1. 概要

RunPod Serverless上でComfyUIを動作させ、静止画生成（Flux）とI2V動画生成（Wan2.1）を行う。PodではなくServerlessを使うことで、リクエスト時のみGPUが起動し、待機中の課金をゼロにする。

静止画とI2Vは別エンドポイントとし、静止画を目視確認してOKが出てからI2Vに進むワークフローとする。

## 2. インフラ構成

- **計算リソース**: RunPod Serverless（GPU: RTX 4090 推奨、フォールバック: RTX 3090）
- **ストレージ**: RunPod Network Volume（マウントパス: `/workspace`）
  - モデル、カスタムノード、設定ファイルを保持
- **ベースイメージ**: runpod/ai-worker-comfyui（公式イメージ）
  - ComfyUIの起動管理は公式イメージが自動で行う
  - handler.pyはワークフローJSONを投げて結果を受け取るだけ
- **並列処理**: Max Workers設定で並列台数を制御

## 3. エンドポイント構成

### エンドポイントA: 静止画生成（Flux）

- **入力**: ComfyUIワークフローJSON（Fluxモデル指定、プロンプト、LoRA設定等）
- **処理**: Fluxで静止画を生成
- **出力**: Network Volume `/workspace/outputs/images/` に保存
- **後続**: ローカルからNetwork Volumeの画像を取得して目視確認

### エンドポイントB: I2V動画生成（Wan2.1）

- **入力**: ComfyUIワークフローJSON（Wan2.1モデル指定、入力画像パス、動きプロンプト等）
- **処理**: 目視確認OKの静止画からWan2.1でI2V動画生成
- **出力**: Network Volume `/workspace/outputs/videos/` に保存
- **後続**: ローカルからNetwork Volumeの動画を取得

## 4. ファイル転送方針

- **GPU上ではNetwork Volumeへの保存のみ行う**（rclone転送はしない）
  - 理由: 転送完了までGPU課金が続くのを避けるため
- **ローカルからの取得**: ローカル側からrclone等でNetwork Volumeのファイルを引っ張る
  - 取得用のスクリプトも別途作成する

## 5. handler.py の要件

### 共通

- 公式イメージ（runpod/ai-worker-comfyui）前提。ComfyUIの起動管理は公式に任せる
- APIリクエストからJSON形式のComfyUIワークフローを受け取る
- モデル名、プロンプト、入力画像パス等のパラメータを動的に置換可能にする
- ローカルのComfyUI API（127.0.0.1:8188）にワークフローを送信し、完了をポーリングで待機
- 生成ファイルをNetwork Volume内の所定ディレクトリに保存
- 処理完了後、保存先パスやステータスをJSONで返却

### エンドポイントA用（静止画）

- Fluxワークフローを受け取って実行
- 生成された画像ファイルを `/workspace/outputs/images/{job_id}/` に保存
- LoRA設定（モデルパス、strength）をリクエストから受け取れるようにする

### エンドポイントB用（I2V動画）

- Wan2.1ワークフローを受け取って実行
- 入力画像のパス（Network Volume上）をリクエストから受け取る
- 生成された動画ファイルを `/workspace/outputs/videos/{job_id}/` に保存
- 動画生成はタイムアウトが長いため、十分な待機時間を設定

## 6. ローカル側スクリプトの要件

### リクエスト送信スクリプト

- Serverless APIにワークフローJSONをPOSTしてジョブIDを取得
- ジョブIDでポーリングして完了を待つ
- 複数ジョブの一括送信（並列生成）に対応
- 環境変数 `RUNPOD_API_KEY` を使用（Pod起動スクリプトと同じ方式）

### ファイル取得スクリプト

- Network Volumeからrclone等で生成ファイルをローカルにダウンロード
- 静止画確認後、OKの画像パスを指定してI2Vリクエストを送信する機能

## 7. 準備フェーズ（Podを使用）

Serverless本番の前に、通常のPodで環境構築とテストを行う。

1. Network Volumeをマウントした GPU Pod を起動
2. ComfyUIのセットアップ
3. カスタムノードのインストール（※下記「確認事項」参照）
4. 必要モデルのダウンロード（Flux、Wan2.1、LoRA等）
5. handler.py の作成と動作確認（デバッグ）
6. 動作確認完了後、Podを削除

## 8. 本番フェーズ（Serverless）

1. Network Volumeを指定してServerless Endpointを作成（A: 静止画、B: I2V動画）
2. ローカルからAPIでリクエスト送信
3. Serverless側で自動的にGPUが起動、Volume内のモデル・設定を参照して実行
4. 生成ファイルをNetwork Volumeに保存
5. ローカルからファイルを取得して確認
6. 全ジョブ終了後、GPUが自動解放

## 9. 料金

- **GPU課金**: 動画/画像を生成している秒数に対してのみ発生（待機0円）
- **ストレージ課金**: Network Volumeのデータ保持量に応じて月額発生
- **rclone転送はローカル側で行うため、GPU課金には影響しない**

## 10. 確認事項・TODO

- [ ] **カスタムノードの一覧確認**: 現在PodのComfyUIで使っているカスタムノードを特定する（`/workspace/ComfyUI/custom_nodes/` を `ls` で確認）。公式Serverlessイメージに含まれていないものはNetwork Volumeに配置してマウント時に読み込ませる設定が必要
- [ ] **公式イメージのバージョン確認**: runpod/ai-worker-comfyui がFlux、Wan2.1に対応しているか確認
- [ ] **タイムアウト設定**: エンドポイントBのI2V動画生成は処理時間が長い。Serverlessのタイムアウト上限を確認し、十分な値を設定
- [ ] **GPU在庫**: RTX 4090が在庫切れの場合のフォールバック（RTX 3090）をエンドポイント設定で対応可能か確認
- [ ] **コールドスタート時間**: 初回起動時のモデルロード時間を計測し、実用的か確認

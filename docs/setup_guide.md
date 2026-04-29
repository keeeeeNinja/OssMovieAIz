# OssMovieAIz Serverless セットアップガイド（視聴者向け）

## Step 1: 秘密情報ディレクトリの作成

ターミナルで以下を実行：

```bash
mkdir -p ~/.config/ossmovie
```

## Step 2: 設定ファイルのコピー

プロジェクトディレクトリに移動し、`.env.example` をコピー：

```bash
cp .env.example ~/.config/ossmovie/.env
```

## Step 3: 設定ファイルを開いて値を入力

Cursor で開く：

```bash
cursor ~/.config/ossmovie/.env
```

各キーに対応する値を入力して保存。

## Step 4: 動作確認

プロジェクトディレクトリで以下を実行：

```bash
python3 -c "from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path.home() / '.config' / 'ossmovie' / '.env'); import os; print('OK' if os.getenv('RUNPOD_API_KEY') else 'NG: 値が読めません')"
```

`OK` が表示されればセットアップ完了。

## 補足：なぜホーム配下に置くのか

秘密情報をプロジェクトディレクトリの中に置くと、うっかり GitHub にアップロードしてしまう事故が起きやすくなります。
ホーム配下の専用ディレクトリに置くことで、そのリスクを構造的に防いでいます。

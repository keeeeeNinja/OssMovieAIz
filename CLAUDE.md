# OssMovieAIz — AI動画広告制作プロジェクト

## WHY
Wan 2.1（ComfyUI on RunPod **Serverless**）でAI動画を生成し、Remotionでテロップ・BGM・ナレーションを合成してショート動画広告を完成させる。Pod 起動・SSH 運用は廃止し、`scripts/serverless_request.py` 経由で投入する構成。

## プロジェクト構成
```
OssMovieAIz/
├── 作業中動画/           # テーマごとにサブフォルダを使用
│   ├── プロンプト.md     #   全テーマ共通の構成案
│   ├── theme1/           #   flux_C01.png〜, scene_C01_wan21.mp4〜
│   ├── theme2/
│   ├── theme3/
│   ├── theme4/
│   └── theme5/           # 1つのbs構造から最大5テーマを展開
├── public/               # Remotion用アセット（動画・bgm.mp3・narration.wav）
├── src/compositions/
│   └── AdVideo.tsx       # Remotionコンポジション
├── .claude/skills/       # スキル定義（Claude Code自動検出）
│   ├── wan-video/        # Wan 2.1 I2V（メイン動画生成エンジン）
│   ├── kling-video/      # Kling（fal.ai経由）
│   ├── pixverse-prompt/  # PixVerse
│   ├── runway-video/     # Runway（MCP経由）
│   ├── video-script/     # ナレーション・BGM・音声生成
│   └── telop-design/     # テロップデザイン設計・実装
├── scripts/
│   ├── generate_tts_qwen3.py    # Qwen3-TTS Serverless 音声生成（商用OK）
│   ├── generate_tts_irodori.py  # 旧 Irodori-TTS（非推奨・互換ラッパー）
│   └── generate_music.py        # ACE-Step BGM生成
├── remotion.config.ts
├── tsconfig.json
├── package.json
└── CLAUDE.md
```

## コマンド
- **プロジェクト初期化**: `bash scripts/reset_project.sh` — AdVideo.tsxをテンプレートに戻し、public/・作業中動画/をクリア（theme1〜5フォルダは再作成）
- Remotion Studio: `npm run studio` → http://localhost:3000
- レンダー: `npm run render` → `out/ad-video.mp4`
- 音声生成: `python3 scripts/generate_tts_qwen3.py --text "..." --reference QwenTTS/reference_qwen_female_v1.wav --output public/narration.wav`（Qwen3-TTS Serverless / Apache 2.0）
- BGM生成: `python3 scripts/generate_music.py --caption "..." --duration 30 --output public/bgm.mp3`（30秒超は自動分割。`--caption2`で後半の雰囲気を変更可）
- ACE-Step: APIサーバー起動必須（localhost:8001）
- 動画メタデータ: `ffmpeg -i <file>`
- フレーム抽出: `ffmpeg -i <file> -vf "select=eq(n\,0)" -vsync vr frame.png`

## 絶対ルール
- **テロップはbs分析結果をベースにし、映像に合わない部分だけ調整する。前回の動画から流用しない**
- **テロップ文言はbsの文字数帯・役割を維持する。短いキャッチコピーを長い説明文に膨らませない**
- デザインの良し悪しは `デザインの極意書.md` のチェックリストで判断する
- 勝手に大きく変えない。方針は必ずユーザーに確認する

## 動画制作フロー
詳細は `/video-pipeline` スキル（`.claude/skills/video-pipeline/SKILL.md`）参照。バズ動画URL受領または「動画作って」「初期化して」で発火。Step -1〜10 の手順・⚠️ TaskCreate ルールはすべてスキル内に集約。

## クリップ生成エンジン
通常フローは Wan 2.1 (Serverless) で固定。Kling/Runway/PixVerse スキルは `.claude/skills/_archive/` に退避済み。

| エンジン | 強み | コスト | スキル |
|---------|------|--------|-------|
| **Wan 2.1 (Serverless)** | OSS・低コスト・参照画像に忠実・コールドスタート 6 秒 | 約 $0.09/clip（exec 7.5 分 × 4090） | `/wan-video` |

## RunPod Serverless 環境
- カスタムイメージ: `ghcr.io/keeeeeninja/ossmovie-comfyui:v1.0.0`（GitHub Actions ビルド）
- ワーカー GPU: RTX 4090（FlashBoot 有効、コールドスタート約 6 秒）
- Network Volume `c1dbeweh5j` を `/workspace` にマウント → Flux fp8 / LoRA / Wan 2.1 I2V 14B (GGUF Q5_K_M) を共有
- 環境変数:
  - `RUNPOD_API_KEY` → `~/.zshrc`（手動入力。Claude が誤って zshrc を編集しない）
  - `RUNPOD_ENDPOINT_FLUX` / `RUNPOD_ENDPOINT_I2V` → `.env`（プロジェクトコミットせず）
  - `SERVERLESS_IMAGE` → `.env`（イメージタグの固定）
- 投入: `python3 scripts/serverless_request.py --endpoint {flux,i2v} ...`（base64 input/output で完結。`--save-locally` でローカル decode）
- ヘルス確認: `https://api.runpod.ai/v2/<ENDPOINT_ID>/health`（無料・課金無し）
- 構築仕様: `AI動画生成＆LoRA学習環境 構築仕様書.md`（**Pod 運用章は歴史的経緯として保持。現行は Serverless**）

### マルチテーマ運用
- プロンプト JSON は 1 ファイル（`scripts/flux_prompts.json` / `scripts/wan_i2v_prompts.json`）に全テーマの id（`T1_C01` / `T2_C01` ...）を混在させる
- `--output-root 作業中動画` を渡すと id の `T{N}_` プレフィックスから `作業中動画/theme{N}/` へ自動ルーティング
- 並列度は Serverless ワーカープールが裁く。ローカル側の lock（`作業中動画/.locks_serverless_{flux,i2v}/`）は同 id の二重投入防止のみ
- Flux PNG は Wan 投入時に `--image-file` で base64 注入（ローカル中継）。Pod 間 SCP 中継は不要

## スキル一覧
| スキル | 用途 |
|-------|------|
| **bs** (buzz-skeleton) | 参考バズ動画を分析 → カット割り・テンポ・テロップスタイルを抽出（Step 2） |
| `/plan-video` | bs分析のカット数・尺配分をベースにストーリー構成を設計（Step 4） |
| `/telop-baseline` | bs抽出したテロップスタイル・原文を黒背景のAdVideo.tsxに実装（Step 5） |
| `/flux-image` | 各シーンのFlux用静止画プロンプトを生成し、Serverless で一括生成（Step 6） |
| `/wan-video` | Wan 2.1 I2V を RunPod Serverless 経由でクリップ生成（Step 7） |
| `/telop-design` | 映像完成後にbsスタイルをベースに差分調整＋文言作成・AdVideo.tsx実装（Step 8） |
| `/video-script` | ナレーション原稿作成・BGM生成・Qwen3-TTS音声生成（Step 9） |
| `/runpod-start` | （非推奨）通常フローでは使用しない。LoRA 学習など Pod が必要な例外用途のみ |

退避済み（`.claude/skills/_archive/`）: `/kling-video` `/runway-video` `/pixverse-prompt` `/flux-face-prompt`

## テロップ・AdVideo.tsx 構築ルール
詳細は `.claude/skills/telop-baseline/SKILL.md` と `.claude/skills/telop-design/SKILL.md` 参照。要点のみ：
- **真実の出典は `作業中動画/bs_composition.json`**（bs MCP の `analyze_video` 戻り値を保存したもの）。telop-baseline / telop-design はこの JSON だけを入力にする
- **AdVideo.tsx は Read しない**。前回コードに引きずられる事故を防ぐため、JSON から毎回ベタ書きで再構築する
- **発動タイミング**:
  - Step 5 = `/telop-baseline`（クリップ未生成・黒背景プレビュー）
  - Step 8a（Phase A） = `/telop-design`（Wan 生成と並行・文言だけ書き換え）
  - Step 8b（Phase B） = `/telop-design`（クリップ完成後・スタイル相性チェック）
- **アーキテクチャは B+共通**: `shared.tsx` の `AdVideoBase` / `animC` / `Clip` 型だけを import し、テロップ表現は各シーンの `render` 内に直書きする。`telopBase` `wrapperBase` は使わない
- **テロップ 1 行制約**: バズ動画が 1 行テロップなら新文言も 1 行。文字数が増えるなら `fontSize` を直書きで縮小して収める（自動縮小関数は使わない）
- **AdVideo.tsx 実装時は Write ツールを使わず、Bash のヒアドキュメント（`cat <<'EOF'`）で上書きする**

## Remotion
- 縦型 1080×1920 / 30fps
- AdVideo.tsx: clips配列でSequenceを繋ぐ
- 音声: `public/bgm.mp3` + `public/narration.wav`
- **ナレーション音量のデフォルト: `volume={0.4}`**（1.0だと大きすぎる）
- クリップ: `public/` に配置（staticFile参照）

## 参照ドキュメント
| ファイル | 用途 |
|---------|------|
| `デザインの極意書.md` | デザイン判断基準 |
| `AI動画生成＆LoRA学習環境 構築仕様書.md` | 環境構築の全手順（旧 Pod 章は歴史的参照） |
| `RunPodの運用方法.md` | （旧）Pod 運用ガイド。Serverless 移行後は LoRA 学習等の例外用途のみ |
| `pod起動コマンド.md` | （旧）Pod 起動・SSH 接続。同上 |
| `serverless_次回作業指示.md` | Serverless 構築の経緯・S3 連携メモ |

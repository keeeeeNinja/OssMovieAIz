# OssMovieAIz — AI動画広告制作プロジェクト

## WHY
Wan 2.1（ComfyUI on RunPod）でAI動画を生成し、Remotionでテロップ・BGM・ナレーションを合成してショート動画広告を完成させる。

## プロジェクト構成
```
OssMovieAIz/
├── 作業中動画/           # 素材画像 + 生成クリップ + プロンプト.md + テロップとナレーション.md
├── public/               # Remotion用アセット（動画・bgm.mp3・narration.wav）
├── src/compositions/
│   └── AdVideo.tsx       # Remotionコンポジション
├── .claude/skills/       # スキル定義（Claude Code自動検出）
│   ├── wan-video/        # Wan 2.1 I2V（メイン動画生成エンジン）
│   ├── kling-video/      # Kling（fal.ai経由）
│   ├── pixverse-prompt/  # PixVerse
│   ├── runway-video/     # Runway（MCP経由）
│   ├── video-script/     # テロップ・ナレーション・音声生成
│   └── telop-design/     # テロップデザイン設計・実装
├── scripts/
│   ├── generate_tts_irodori.py  # Irodori-TTS VoiceDesign音声生成
│   └── generate_music.py        # ACE-Step BGM生成
├── remotion.config.ts
├── tsconfig.json
├── package.json
└── CLAUDE.md
```

## コマンド
- Remotion Studio: `npm run studio` → http://localhost:3000
- レンダー: `npm run render` → `out/ad-video.mp4`
- 音声生成: `python3 scripts/generate_tts_irodori.py --text "..." --caption "声の説明" --output public/narration.wav`
- BGM生成: `python3 scripts/generate_music.py --caption "..." --duration 30 --output public/bgm.mp3`（30秒超は自動分割。`--caption2`で後半の雰囲気を変更可）
- ACE-Step: APIサーバー起動必須（localhost:8001）
- 動画メタデータ: `ffmpeg -i <file>`
- フレーム抽出: `ffmpeg -i <file> -vf "select=eq(n\,0)" -vsync vr frame.png`

## 絶対ルール
- **テロップはbs分析結果（配置・色・フォント）をそのまま使う。前回の動画から流用しない**
- デザインの良し悪しは `デザインの極意書.md` のチェックリストで判断する
- 勝手に大きく変えない。方針は必ずユーザーに確認する

## 動画制作フロー（デフォルト）
1. **参考動画の提示**: ユーザーがバズ動画のURLを提示する
2. **bs分析**: buzz-skeleton（bs）で参考動画を分析 → カット割り・テンポ・トランジション・テロップスタイルを抽出
3. **テロップ再現（丸パクリ）**: bs分析結果のテロップスタイル（配置・色・フォント・サイズ・文言）をそのままAdVideo.tsxに実装する。
   1. AdVideo.tsxに実装（バズ動画の原文をそのまま使う）
   2. `npm run studio` でRemotionを起動し、ユーザーに確認してもらう
   3. ユーザー承認後、次のステップへ進む
   ※ テロップの文言はStep 8で差し替える
4. **テーマ確認**: ユーザーがこの動画のテーマを伝える
5. **ストーリー設計**: bs分析結果＋テーマからストーリー構成を設計（シーン数・各シーンの尺・感情フロー・カメラワーク）→ ユーザー承認
6. **静止画プロンプト作成**: 各シーンのI2V用静止画を生成するプロンプトを作成 → 画像生成（Flux等）
7. **クリップ生成**: `/wan-video`（Wan 2.1）または `/kling-video` `/runway-video` `/pixverse-prompt` で動画クリップを生成
8. **ナレーション・テロップ文言差し替え・BGM**:
   - `/video-script` → テロップ文言差し替え・ナレーション原稿 → Irodori-TTS音声生成 → `public/narration.wav`
   - テロップスタイル（配置・色・フォント・サイズ）はStep 3で実装済み。ここでは文言のみ差し替える
   - BGM: `python3 scripts/generate_music.py` → `public/bgm.mp3`
   - **ナレーション尺の目安: 動画尺 - 3秒**（動画と同じ長さだと余韻がなくなる）
9. **合成・レンダー**: クリップを `public/` にコピー → Remotionで合成 → `npm run render`

## クリップ生成エンジンの使い分け
| エンジン | 強み | コスト | スキル |
|---------|------|--------|-------|
| **Wan 2.1** | OSS・自前GPU・低コスト・参照画像に忠実 | ~$0.05/clip(GPU時間) | `/wan-video` |
| **Kling** | 人物動作が安定・商用品質 | $0.28〜$1.40/clip | `/kling-video` |
| **Runway** | シネマティック・光と大気感 | $0.25〜$0.60/clip | `/runway-video` |
| **PixVerse** | 複数素材の合成（Fusion） | 従量 | `/pixverse-prompt` |

## RunPod環境
- GPU: RTX 4090（VRAM 24GB）
- ComfyUI: `/workspace/ComfyUI/`（port 8188）
- モデル: Wan 2.1 I2V 14B（Q5_K_M GGUF）
- SSH/SCPコマンドは一括許可済み（settings.local.json）
- SSH接続情報はPod再起動ごとに変わる → `pod起動コマンド.md` 参照
- SSHキー設定: `ssh.md` 参照
- 運用ガイド: `RunPodの運用方法.md`
- 構築仕様: `AI動画生成＆LoRA学習環境 構築仕様書.md`

### 複数Pod並列運用
- Network Volumeは同時に1つのPodにしかマウントできない
- **Pod 1**: Network Volume付き → 即使用可能
- **Pod 2以降**: Volume なし → `setup_comfyui.sh` をJupyterで実行（約5-10分でモデルDL完了）
- 全Pod準備完了後、各Podに1クリップずつ割り当てて一斉生成

## スキル一覧
| スキル | 用途 |
|-------|------|
| **bs** (buzz-skeleton) | 参考バズ動画を分析 → カット割り・テンポ・テロップスタイルを抽出。動画制作フローのStep 2で使用 |
| `/wan-video` | Wan 2.1 I2VでRunPod上のComfyUI経由でクリップ生成。SSH+API |
| `/kling-video` | Kling v2.1/v3でクリップ生成（fal.ai経由） |
| `/runway-video` | Runway gen4_turbo/gen4.5でクリップ生成（MCP経由） |
| `/pixverse-prompt` | PixVerse Image-to-Video / Fusion Videoのプロンプト生成 |
| `/video-script` | テロップ文言・ナレーション・Irodori-TTS音声生成 |
| `/telop-design` | bs抽出テロップスタイルをベースにデザイン設計・AdVideo.tsx実装 |

## telop-designスキルの設計
- **テロップスタイルはbs分析結果をそのまま使う**（配置・色・フォント・サイズ）
- パターン辞書: `.claude/skills/telop-design/patterns.md`（参考用。bs結果が不十分な場合の補完に使う）
- フォント・色・装飾: `.claude/skills/telop-design/fonts-colors-decorations.md`（実装時の技術リファレンス）
- AdVideo.tsxはインラインスタイル構成（clips配列 + render関数で全パターン対応）
- **デフォルトアニメーション**: 全シーン共通で `animC`（タイプライター式blurフェードイン）
- **テロップ1行制約**: バズ動画が1行テロップの場合、オリジナルのテキストが長くても改行せずフォントサイズを縮小して必ず1行に収める。`calcFontSize()`で基準文字数・基準サイズから自動算出する
- **AdVideo.tsx実装時はWriteツールを使わず、Bashのヒアドキュメント（`cat <<'EOF'`）で上書きする**

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
| `AI動画生成＆LoRA学習環境 構築仕様書.md` | RunPod環境構築の全手順 |
| `RunPodの運用方法.md` | Pod運用ガイド |
| `pod起動コマンド.md` | Pod起動・SSH接続 |

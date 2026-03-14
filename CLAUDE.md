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
├── skills/               # スキル定義
│   ├── wan-video/        # Wan 2.1 I2V（メイン動画生成エンジン）
│   ├── kling-video/      # Kling（fal.ai経由）
│   ├── pixverse-prompt/  # PixVerse
│   ├── runway-video/     # Runway（MCP経由）
│   ├── video-script/     # テロップ・ナレーション・音声生成
│   └── telop-design/     # テロップデザイン設計・実装
├── scripts/
│   ├── generate_tts.py   # VOICEVOX音声生成
│   └── generate_music.py # ACE-Step BGM生成
├── remotion.config.ts
├── tsconfig.json
├── package.json
└── CLAUDE.md
```

## コマンド
- Remotion Studio: `npm run studio` → http://localhost:3000
- レンダー: `npm run render` → `out/ad-video.mp4`
- 音声生成: `python3 scripts/generate_tts.py --text "..." --voicevox-id ID --output public/narration.wav`
- BGM生成: `python3 scripts/generate_music.py --caption "..." --duration 30 --output public/bgm.mp3`
- VOICEVOX: GUIアプリ起動必須（localhost:50021）
- ACE-Step: APIサーバー起動必須（localhost:8001）
- 動画メタデータ: `ffmpeg -i <file>`
- フレーム抽出: `ffmpeg -i <file> -vf "select=eq(n\,0)" -vsync vr frame.png`

## 絶対ルール
- **テロップは毎回ゼロから設計する。前回の動画のフォント・サイズ・配置・色・装飾を絶対に流用しない**
- bannnner.com のバナーを「元ネタ」として使い、そのデザイン処理をそのまま適用する
- 各シーンの参考バナー画像をユーザーに提示し、承認を得てから実装する
- デザインの良し悪しは `デザインの極意書.md` のチェックリストで判断する
- 勝手に大きく変えない。方針は必ずユーザーに確認する

## 動画制作フロー
1. 素材画像を `作業中動画/` に入れる
2. クリップ生成: `/wan-video`（Wan 2.1）または `/kling-video` `/runway-video` `/pixverse-prompt`
3. `/video-script` → テロップ・ナレーション原稿 → VOICEVOX音声生成 → `public/narration.wav`
4. `/telop-design` → bannnner.comパターン辞書からデザイン導出 → AdVideo.tsx実装
5. BGM: `python3 scripts/generate_music.py` → `public/bgm.mp3`
6. クリップを `public/` にコピー → `npm run render`

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
| `/wan-video` | Wan 2.1 I2VでRunPod上のComfyUI経由でクリップ生成。SSH+API |
| `/kling-video` | Kling v2.1/v3でクリップ生成（fal.ai経由） |
| `/runway-video` | Runway gen4_turbo/gen4.5でクリップ生成（MCP経由） |
| `/pixverse-prompt` | PixVerse Image-to-Video / Fusion Videoのプロンプト生成 |
| `/video-script` | テロップ文言・ナレーション・音声生成（VOICEVOX） |
| `/telop-design` | bannnner.comパターン辞書を使ったテロップデザイン設計・AdVideo.tsx実装 |

## telop-designスキルの設計
- パターン辞書: `skills/telop-design/patterns.md`（10パターン、CSS実装例付き）
- マッチングルール: `skills/telop-design/matching-rules.md`（映像→パターン判定フロー）
- フォント・色・装飾: `skills/telop-design/fonts-colors-decorations.md`
- 代表バナー画像: `skills/telop-design/banners/`（P1〜P10各1枚）
- AdVideo.tsxはインラインスタイル構成（clips配列 + render関数で全パターン対応）
- **デフォルトアニメーション**: 全シーン共通で `animC`（タイプライター式blurフェードイン）
- **AdVideo.tsx実装時はWriteツールを使わず、Bashのヒアドキュメント（`cat <<'EOF'`）で上書きする**

## Remotion
- 縦型 1080×1920 / 30fps
- AdVideo.tsx: clips配列でSequenceを繋ぐ
- 音声: `public/bgm.mp3` + `public/narration.wav`
- クリップ: `public/` に配置（staticFile参照）

## 参照ドキュメント
| ファイル | 用途 |
|---------|------|
| `デザインの極意書.md` | デザイン判断基準 |
| `AI動画生成＆LoRA学習環境 構築仕様書.md` | RunPod環境構築の全手順 |
| `RunPodの運用方法.md` | Pod運用ガイド |
| `pod起動コマンド.md` | Pod起動・SSH接続 |

# OssMovieAIz — AI動画広告制作プロジェクト

## WHY
Wan 2.1（ComfyUI on RunPod）でAI動画を生成し、Remotionでテロップ・BGM・ナレーションを合成してショート動画広告を完成させる。

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
│   ├── generate_tts_irodori.py  # Irodori-TTS VoiceDesign音声生成
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
- 音声生成: `python3 scripts/generate_tts_irodori.py --text "..." --caption "声の説明" --output public/narration.wav`
- BGM生成: `python3 scripts/generate_music.py --caption "..." --duration 30 --output public/bgm.mp3`（30秒超は自動分割。`--caption2`で後半の雰囲気を変更可）
- ACE-Step: APIサーバー起動必須（localhost:8001）
- 動画メタデータ: `ffmpeg -i <file>`
- フレーム抽出: `ffmpeg -i <file> -vf "select=eq(n\,0)" -vsync vr frame.png`

## 絶対ルール
- **テロップはbs分析結果をベースにし、映像に合わない部分だけ調整する。前回の動画から流用しない**
- **テロップ文言はbsの文字数帯・役割を維持する。短いキャッチコピーを長い説明文に膨らませない**
- デザインの良し悪しは `デザインの極意書.md` のチェックリストで判断する
- 勝手に大きく変えない。方針は必ずユーザーに確認する

## 動画制作フロー（デフォルト）
-1. **初期化**: ユーザーが「初期化して」と言ったら `bash scripts/reset_project.sh` を実行。AdVideo.tsx・public/・作業中動画/ を前回の動画から完全にリセットする。**次の動画制作は必ず初期化後に始める**
0. **RunPod起動（バックグラウンド）**: 動画制作フローを開始する時点で、サブエージェント（`run_in_background: true`）で `/runpod-start` を実行する。メインはStep 1以降を並行して進める。クリップ生成（Step 7）までにPodが準備完了していればOK
1. **参考動画の提示**: ユーザーがバズ動画のURLを提示する
2. **bs分析**: buzz-skeleton（bs）で参考動画を分析 → カット割り・テンポ・トランジション・テロップスタイルを抽出
3. **テーマ確認**: ユーザーがこの動画のテーマを伝える
4. **ストーリー設計**: `/plan-video` — bs分析のカット数・尺配分をベースに、テーマに合わせて微調整する。各シーンの役割・秒数・カメラワーク・推奨エンジンを設計 → ユーザー承認 → `作業中動画/プロンプト.md` に保存（全テーマ共通）
5. **テロップ構造実装（bsベースライン）**: bs分析結果のテロップスタイル（配置・色・フォント・サイズ・文言）をStep 4で確定した構成に合わせてAdVideo.tsxに実装する。
   1. AdVideo.tsxに実装（バズ動画の原文・スタイルをそのまま使う。カット数・尺はStep 4の構成に従う）
   2. `npm run studio` でRemotionを起動し、ユーザーに確認してもらう
   3. ユーザー承認後、次のステップへ進む
   ※ このスタイルは「ベースライン」。Step 8で実映像に合わせて調整する
6. **静止画生成**: `/flux-image` — bs分析＋plan-video構成案から各シーンのFlux用プロンプトを自動生成し、RunPod上のComfyUIで一括生成
   - 顔の一貫性はLoRAで担保する前提（PuLID・ペルソナデータ・flux-face-promptは使わない）
   - プロンプトには顔の詳細を書かない（衣装・ポーズ・背景・ライティング・構図・表情・品質タグのみ）
   - フロー: テーマ・LoRA確認 → プロンプト生成 → `scripts/flux_prompts.json` 保存 → `scripts/generate_flux_images.py --output-dir 作業中動画/themeN` で一括生成
   - **複数テーマの場合**: 同じbs構造のプロンプトをテーマごとに書き換え、`--output-dir` でテーマフォルダに分けて生成
7. **クリップ生成**: `/wan-video`（Wan 2.1）または `/kling-video` `/runway-video` `/pixverse-prompt` で動画クリップを生成
   - `--output-dir 作業中動画/themeN` / `--image-dir 作業中動画/themeN` でテーマフォルダを指定
8. **クリップ配置＋テロップ最適化**: クリップ生成完了後、以下を行う：
   1. 生成されたクリップを `public/` にコピーし、AdVideo.tsxのファイル名を実際のクリップ名に合わせる
   2. `/telop-design` — bsスタイルをベースに実映像との相性をチェックし、問題があるシーンだけスタイル調整。同時にテロップ文言もbsの文字数・役割を維持して新テーマに書き換える
9. **ナレーション・BGM**: `/video-script` — ナレーション原稿作成・Irodori-TTS音声生成・BGM生成まで一括で行う
   - ※ テロップ文言はStep 8で決定済み
   - **ナレーション尺の目安: 動画尺 - 3秒**（動画と同じ長さだと余韻がなくなる）。**文字数の目安: 目標秒数 × 4文字**（Irodori-TTSは1秒約4文字のペース）
10. **レンダー**: `npm run render` → `out/ad-video.mp4`

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
- **Pod 1**: Network Volume付き → `/runpod-start` で起動
- **Pod 2以降**: Volume なし → `scripts/setup_parallel_pod.py` で作成・セットアップ・画像アップロードまで一気通貫
- 全Pod準備完了後、`scripts/generate_wan_i2v.py` を各Podに対して `Bash(run_in_background: true)` で並列実行
- **空きPodは未着手クリップを自動で引き受ける**: 全Podに全シーンを渡せば、ロック機構で自動分配される。担当分が終わったPodは待機せず次の未生成クリップを取りに行く

```bash
# 推奨: 全シーンを渡してロックで自動分配（空きPodが未着手を自動引き受け）
python3 scripts/generate_wan_i2v.py \
  --host $IP --port $PORT \
  --prompts scripts/wan_i2v_prompts.json \
  --output-dir 作業中動画/theme1

# Pod 2以降の起動（セットアップ + 画像アップロード + Wan生成まで一括）
python3 scripts/setup_parallel_pod.py \
  --scenes T1_C06,T1_C07,T1_C08,T1_C09,T1_C10 \
  --prompts scripts/wan_i2v_prompts.json \
  --image-dir 作業中動画/theme1 \
  --generate

# セットアップのみ（生成は別途実行）
python3 scripts/setup_parallel_pod.py \
  --scenes T2_C01,T2_C02,T2_C03,T2_C04,T2_C05

# 既存Podに対して実行
python3 scripts/setup_parallel_pod.py \
  --pod-id xl19hfyvee2834 \
  --scenes T2_C06,T2_C07,T2_C08,T2_C09,T2_C10
```

**重要: SSH/SCP操作はサブエージェント（Agent tool）に委任しない。** サブエージェントはBash権限が別管理のため拒否される。Pythonスクリプトをメイン会話から `Bash(run_in_background: true)` で直接実行すること。

## スキル一覧
| スキル | 用途 |
|-------|------|
| **bs** (buzz-skeleton) | 参考バズ動画を分析 → カット割り・テンポ・テロップスタイルを抽出。動画制作フローのStep 2で使用 |
| `/wan-video` | Wan 2.1 I2VでRunPod上のComfyUI経由でクリップ生成。SSH+API |
| `/kling-video` | Kling v2.1/v3でクリップ生成（fal.ai経由） |
| `/runway-video` | Runway gen4_turbo/gen4.5でクリップ生成（MCP経由） |
| `/pixverse-prompt` | PixVerse Image-to-Video / Fusion Videoのプロンプト生成 |
| `/plan-video` | bs分析のカット数・尺配分をベースにストーリー構成を設計（Step 4） |
| `/video-script` | ナレーション原稿作成・BGM生成・Irodori-TTS音声生成（Step 9） |
| `/telop-design` | 映像完成後にbsスタイルをベースに差分調整＋文言作成・AdVideo.tsx実装（Step 8） |
| `/runpod-start` | RunPod API経由でPod起動 → SSH確認 → ComfyUIセットアップ → ssh.md更新まで一気通貫 |
| `/flux-image` | bs分析＋plan-video構成案から各シーンのFlux用静止画プロンプトを生成し、RunPodで一括生成（Step 6） |
| `/flux-face-prompt` | 画像から顔を超詳細に分析し、Flux向け英語プロンプトを生成。※現在はLoRAベースの顔一貫性に移行したため通常フローでは使用しない |

## telop-designスキルの設計
詳細は `.claude/skills/telop-design/SKILL.md` 参照。要点のみ：
- **発動タイミング**: Step 8（映像クリップ完成後）
- **方針**: bsスタイルをベースに、実映像に合わない部分だけ差分調整
- **テロップ1行制約**: バズ動画が1行テロップの場合、改行せずフォントサイズ縮小で1行に収める（`calcFontSize()`）
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

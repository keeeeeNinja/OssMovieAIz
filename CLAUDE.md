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

**⚠️ フロー開始時の必須作業**: ユーザーがバズ動画URLを貼った直後、**Step 2（bs分析）を実行する前に** `TaskCreate` で Step -1〜10 を一括タスク化する。これで「今どのStepか」がユーザーに常に見える状態を作る。テーマ数が Step 3 で確定した時点で、Step 6/7/8 をテーマ別サブタスクに展開する（最初から theme1/2/3 を並べない。Step 3 まではテーマ数が不明なので）。

-1. **初期化**: ユーザーが「初期化して」と言ったら `bash scripts/reset_project.sh` を実行。AdVideo.tsx・public/・作業中動画/ を前回の動画から完全にリセットする。**次の動画制作は必ず初期化後に始める**
0. **RunPod起動（バックグラウンド）**: 動画制作フローを開始する時点で、サブエージェント（`run_in_background: true`）で `/runpod-start` を実行する。メインはStep 1以降を並行して進める。クリップ生成（Step 7）までにPodが準備完了していればOK
1. **参考動画の提示**: ユーザーがバズ動画のURLを提示する
2. **bs分析**: buzz-skeleton（bs）で参考動画を分析 → カット割り・テンポ・トランジション・テロップスタイルを抽出
3. **テーマ確認**: ユーザーがこの動画のテーマを伝える
4. **ストーリー設計**: `/plan-video` — bs分析のカット数・尺配分をベースに、テーマに合わせて微調整する。各シーンの役割・秒数・カメラワーク・推奨エンジンを設計 → ユーザー承認 → `作業中動画/プロンプト.md` に保存（全テーマ共通）
5. **テロップ構造実装（bsベースライン）**: `/telop-baseline` — bs分析結果のテロップスタイル（配置・色・フォント・サイズ・文言）をAdVideo.tsxに実装し、黒背景でRemotion確認する
   - `clip.file` は **空文字 `""`** にする（`shared.tsx` が空文字のとき `OffthreadVideo` をスキップして黒背景＋テロップだけ描画）
   - 文言は bs 原文のまま（書き換えは Step 8 の `/telop-design`）
   - `src/compositions/shared.tsx` の `AdVideoBase` / `telopBase` / `wrapperBase` / `animC` を import して実装
   - ユーザー承認後に次のステップへ進む
   ※ このスタイルは「ベースライン」。Step 8で実映像に合わせて調整する
6. **静止画生成**: `/flux-image` — bs分析＋plan-video構成案から各シーンのFlux用プロンプトを自動生成し、RunPod上のComfyUIで生成
   - 顔の一貫性はLoRAで担保する前提（PuLID・ペルソナデータ・flux-face-promptは使わない）
   - プロンプトには顔の詳細を書かない（衣装・ポーズ・背景・ライティング・構図・表情・品質タグのみ）
   - **単一テーマ**: Pod 1 で `scripts/generate_flux_images.py --host $POD1 ... --output-dir 作業中動画/theme1` を実行
   - **複数テーマ（マルチPod運用）= プール方式**: 全Podに**全シーン（テーマ混在）**を渡し、ロックで未着手シーンを取り合う。各スクリプトに `--output-root 作業中動画` を指定すると、シーンIDの `T{N}_` プレフィックスから自動で `作業中動画/theme{N}/flux_*.png` にルーティングされる。テーマ境界に縛られず、空いたPodはどのテーマのどのカットでも即座に取りにいく
   - プロンプトJSONは1ファイル（`scripts/flux_prompts.json`）に全テーマの id（`T1_C01`, `T2_C01`, `T3_C01`...）を混在させる
7. **クリップ生成**: `/wan-video`（Wan 2.1）または `/kling-video` `/runway-video` `/pixverse-prompt` で動画クリップを生成
   - 単一テーマ: `--output-dir 作業中動画/themeN`
   - **マルチテーマ（プール方式）**: 各Podが全シーンを受け取って `--output-root 作業中動画` でロック分配。`setup_parallel_pod.py --output-root 作業中動画 --flux-prompts ... --wan-prompts ... --generate` 一本で Flux→Wan 一気通貫
   - **Flux画像のPod間共有**: Pod 1 が T2_C03 の Flux を生成 → ローカル `theme2/` にダウンロード → Pod 2 が Wan で T2_C03 を引き取るときに `generate_wan_i2v.py` がローカルからSCPアップロード（ローカルMacが中継点）。Wan の per-scene ループは Flux 画像がローカルに現れるまで最大10分待機する
   - **Wanは `run_in_background: true` で背景実行**。メイン会話は空くので、この間に Step 8a（文言書き換え）を必ず並行実施する
8. **クリップ配置＋テロップ最適化**: Step 7 と**並行して**進める2段階構成：
   - **Step 8a（Step 7 と並行・クリップ不要）**: `/telop-design` の**文言書き換え部分だけ**先行実装
      - bsテロップの文字数・役割を維持して、新テーマに合わせて文言を書き換え
      - AdVideo.tsx の各 clip の render 内テキストを新文言に差し替え（`file` は空文字のまま）
      - Step 5 のベースラインに重ねる形で更新するだけなので、映像がなくても完結する
   - **Step 8b（Step 7 完了後・クリップ必須）**: 残りの実装
      1. 生成されたクリップを `public/` にコピーし、AdVideo.tsx の `file` を実ファイル名に差し替え
      2. `/telop-design` のスタイル相性チェック（ffmpeg でフレーム抽出→被写体との重なり・コントラスト確認）と、問題があるシーンだけパターン変更／数値微調整
      3. Remotion still で各シーンの中間フレームを書き出して最終レビュー
   - **サブエージェントに委任しない**。Wan は `run_in_background` で背景に逃げているのでメイン会話の手は空いている。サブエージェントはメイン context を持たず、Step 8b のBash権限とも競合する
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

### 複数Pod並列運用（役割分離・プール方式）
- Network Volumeは同時に1つのPodにしかマウントできない
- **Pod 1（Flux + Wan）**: Network Volume付き → `/runpod-start` で起動。**Flux画像生成はPod1専用**（NVMe I/Oが速く、fp8モデル初回ロードが安定）
- **Pod 2以降（Wan専用）**: Volume なし → `scripts/setup_parallel_pod.py` で作成。`setup_comfyui.sh --wan-only` でFlux/LoRAをスキップし、Wan 2.1モデルのみインストール（containerDisk 50GBで十分）
- **Wan生成はロック分配**: 全Podが同じシーンリストを受け取り、ロックで未着手を取り合う。テーマ境界は無視。空きPodが出ない
- 各スクリプトに `--output-root 作業中動画` を渡すと、シーンIDの `T{N}_` プレフィックスから `作業中動画/theme{N}/` へ自動ルーティングされる
- **Flux画像のPod間共有**: Pod1がFlux生成 → ローカルにDL → Pod2以降がWan実行時に `generate_wan_i2v.py` がローカルからSCPアップロード（ローカルMacが中継点）
- Wan の per-scene ループは Flux 画像がローカルに現れるまで最大10分待機

```bash
# ── Pod 1（Volume付き）: Flux画像を全シーン生成 ──
python3 scripts/generate_flux_images.py \
  --host $POD1_IP --port $POD1_PORT \
  --prompts scripts/flux_prompts.json \
  --output-root 作業中動画 \
  --lora flux_japanese_girl_v2.safetensors \
  --copy-to-input

# Pod 1 でも Wan を並行実行
python3 scripts/generate_wan_i2v.py \
  --host $POD1_IP --port $POD1_PORT \
  --prompts scripts/wan_i2v_prompts.json \
  --output-root 作業中動画 \
  --pod-id $POD1_ID

# ── Pod 2/3（Wan専用）: Pod作成 → セットアップ(--wan-only) → 画像アップロード → Wan生成 ──
python3 scripts/setup_parallel_pod.py \
  --wan-prompts scripts/wan_i2v_prompts.json \
  --output-root 作業中動画 \
  --generate

# ※ --scenes を省略するとプロンプトJSONの全シーンが対象になる（推奨）
# ※ --flux-prompts は廃止（Pod1専用に統一）
# ※ 単一テーマなら従来どおり --output-dir 作業中動画/theme1 を使う
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
| `/telop-baseline` | bs抽出したテロップスタイル・原文を黒背景のAdVideo.tsxに実装（Step 5） |
| `/video-script` | ナレーション原稿作成・BGM生成・Irodori-TTS音声生成（Step 9） |
| `/telop-design` | 映像完成後にbsスタイルをベースに差分調整＋文言作成・AdVideo.tsx実装（Step 8） |
| `/runpod-start` | RunPod API経由でPod起動 → SSH確認 → ComfyUIセットアップ → ssh.md更新まで一気通貫 |
| `/flux-image` | bs分析＋plan-video構成案から各シーンのFlux用静止画プロンプトを生成し、RunPodで一括生成（Step 6） |
| `/flux-face-prompt` | 画像から顔を超詳細に分析し、Flux向け英語プロンプトを生成。※現在はLoRAベースの顔一貫性に移行したため通常フローでは使用しない |

## telop-designスキルの設計
詳細は `.claude/skills/telop-design/SKILL.md` 参照。要点のみ：
- **発動タイミング**: Step 8（映像クリップ完成後）
- **方針**: bsスタイルをベースに、実映像に合わない部分だけ差分調整
- **テロップ1行制約**: バズ動画が1行テロップの場合、改行せず `telopBase(fontSize, borderWidth)` の fontSize を手動で小さくして1行に収める（shared.tsx に自動縮小関数は無い）
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

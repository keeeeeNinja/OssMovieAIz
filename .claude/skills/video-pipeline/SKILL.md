---
name: video-pipeline
description: ショート動画広告の制作フロー全体を司るスキル。bs分析→plan-video→Flux静止画→Wan動画→テロップ→ナレーション→レンダーまで Step -1〜10 を順守する。ユーザーがバズ動画URLを貼ったとき、「動画作って」「ショート動画作って」「制作開始」「初期化して」「動画制作フロー」と言ったときに必ず起動すること。
---

# 動画制作フロー（デフォルト）

**⚠️ フロー開始時の必須作業**: ユーザーがバズ動画URLを貼った直後、**Step 2（bs分析）を実行する前に** `TaskCreate` で Step -1〜10 を一括タスク化する。これで「今どのStepか」がユーザーに常に見える状態を作る。テーマ数が Step 3 で確定した時点で、Step 6/7/8 をテーマ別サブタスクに展開する（最初から theme1/2/3 を並べない。Step 3 まではテーマ数が不明なので）。

-1. **初期化**: ユーザーが「初期化して」と言ったら `bash scripts/reset_project.sh` を実行。AdVideo.tsx・public/・作業中動画/ を前回の動画から完全にリセットする。**次の動画制作は必ず初期化後に始める**
0. **Serverless 疎通確認**: 動画制作フローを開始する時点で、`scripts/serverless_request.py` の接続先である RunPod Serverless エンドポイント（Flux / I2V）が生きていることを `/health` で確認する。Pod 起動は不要。エンドポイント ID は `.env` の `RUNPOD_ENDPOINT_FLUX` / `RUNPOD_ENDPOINT_I2V`、API キーは `~/.zshrc` の `RUNPOD_API_KEY` を使用する。失敗したらユーザーに報告し、応答があれば Step 1 へ進む
1. **参考動画の提示**: ユーザーがバズ動画のURLを提示する
2. **bs分析**: buzz-skeleton（bs）で参考動画を分析 → カット割り・テンポ・トランジション・テロップスタイルを抽出。**返ってきた JSON 文字列を `作業中動画/bs_composition.json` に保存する（必須）**。これが以降の Step 4/5/8 の唯一の真実の出典になる。スキルが AdVideo.tsx を読まずにこの JSON だけを参照することで、前回の動画コードに引きずられる事故を防ぐ
   ```bash
   # 例: analyze_video の戻り値を JSON ファイルに保存
   echo "$BS_JSON_RESPONSE" > 作業中動画/bs_composition.json
   ```
3. **テーマ確認**: ユーザーがこの動画のテーマを伝える
4. **ストーリー設計**: `/plan-video` — bs分析のカット数・尺配分をベースに、テーマに合わせて微調整する。各シーンの役割・秒数・カメラワーク・推奨エンジンを設計 → ユーザー承認 → `作業中動画/プロンプト.md` に保存（全テーマ共通）
5. **テロップ構造実装（bsベースライン）**: `/telop-baseline` — `bs_composition.json` のテロップスタイル（配置・色・フォント・サイズ・文言 `telop.text`）をそのままAdVideo.tsxに実装し、黒背景でRemotion確認する
   - **入力は `bs_composition.json` のみ**。AdVideo.tsx は読まない（前回コードに引きずられないため）
   - **アーキテクチャは B+共通**: `shared.tsx` の `AdVideoBase` / `animC` / `Clip` 型だけを import し、テロップ表現（フォント・色・配置）は各シーンの `render` 関数内に**ベタ書き**する。`telopBase` `wrapperBase` は使わない（色固定の制約を避けるため）
   - `clip.file` は **空文字 `""`** にする（`AdVideoBase` は `clip.file` が空文字のとき `OffthreadVideo` をスキップして黒背景＋テロップだけ描画）
   - 文言は `telop.text` 原文のまま（書き換えは Step 8 の `/telop-design`）
   - ユーザー承認後に次のステップへ進む
   ※ このスタイルは「ベースライン」。Step 8で実映像に合わせて調整する
6. **静止画生成**: `/flux-image` — bs分析＋plan-video構成案から各シーンのFlux用プロンプトを自動生成し、Serverless（`serverless_request.py --endpoint flux --save-locally`）で生成
   - 顔の一貫性はLoRAで担保する前提（PuLID・ペルソナデータ・flux-face-promptは使わない）
   - プロンプトには顔の詳細を書かない（衣装・ポーズ・背景・ライティング・構図・表情・品質タグのみ）
   - プロンプトJSONは1ファイル（`scripts/flux_prompts.json`）。`--output-root 作業中動画` を渡すと id の `T{N}_` プレフィックスから `作業中動画/theme{N}/` へ自動ルーティングされる
7. **クリップ生成**: `/wan-video`（Wan 2.1 Serverless）で動画クリップを生成
   - 実行方法: `serverless_request.py --endpoint i2v --prompts ... --save-locally`。Flux で生成した PNG は `--image-file` で base64 注入、Volume 経由ではなくローカル中継
   - **`run_in_background: true` で背景実行**。メイン会話は空くので、この間に Step 8a（文言書き換え）を必ず並行実施する
8. **クリップ配置＋テロップ最適化**: Step 7 と**並行して**進める2段階構成：
   - **Step 8a（Step 7 と並行・クリップ不要）**: `/telop-design` の**文言書き換え部分だけ**先行実装
      - bsテロップの文字数・役割を維持して、新テーマに合わせて文言を書き換え
      - AdVideo.tsx の各 clip の render 内テキストを新文言に差し替え（`file` は空文字のまま）
      - Step 5 のベースラインに重ねる形で更新するだけなので、映像がなくても完結する
   - **Step 8b（Step 7 完了後・クリップ必須）**: 残りの実装
      1. 生成されたクリップを `public/` にコピーし、AdVideo.tsx の `file` を実ファイル名に差し替え
      2. `/telop-design` のスタイル相性チェック（ffmpeg でフレーム抽出→被写体との重なり・コントラスト確認）と、問題があるシーンだけパターン変更／数値微調整
      3. Remotion still で各シーンの中間フレームを書き出して最終レビュー
9. **ナレーション・BGM**: `/video-script` — ナレーション原稿作成・Irodori-TTS音声生成・BGM生成まで一括で行う
   - ※ テロップ文言はStep 8で決定済み
   - **ナレーション尺の目安: 動画尺 - 3秒**（動画と同じ長さだと余韻がなくなる）。**文字数の目安: 目標秒数 × 4文字**（Irodori-TTSは1秒約4文字のペース）
10. **レンダー**: `npm run render` → `out/ad-video.mp4`

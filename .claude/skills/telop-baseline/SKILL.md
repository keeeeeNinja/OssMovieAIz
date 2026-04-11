---
name: telop-baseline
description: bs分析結果のテロップスタイル（配置・色・フォント・サイズ・文言）を黒背景のAdVideo.tsxに実装する。制作フローのStep 5で必ず使う。映像クリップが未完成の状態で動くので、clip.file は空文字のまま。「bsベースライン実装」「Step 5」「黒背景のテロップ確認」という場面で使う。
allowed-tools: Read, Bash(cat *), Bash(ls *), Bash(npm *), Bash(mkdir *), Grep, Glob
---

## bsテロップベースライン実装スキル

制作フローのStep 5として発動する。bs分析で抽出したテロップスタイルと**原文文言**をそのまま AdVideo.tsx に実装し、黒背景で Remotion 確認する。文言書き換えは Step 8 の `/telop-design` が担当するので、このスキルでは bs 原文のまま実装する。

---

### 絶対ルール

1. **clip.file は必ず空文字 `""`** — クリップはまだ生成されていない。`src/compositions/shared.tsx` の `AdVideoBase` は `clip.file` が空文字のとき `OffthreadVideo` をスキップして黒背景＋テロップだけ描画する
2. **bs分析のスタイル・文言をそのまま使う** — 文言書き換えは Step 8 の責務。ここでは勝手に書き換えない
3. **Bash ヒアドキュメントで AdVideo.tsx を上書きする** — Write ツールは使わない。前回の AdVideo.tsx を参照しないための強制リセット
4. **`src/compositions/shared.tsx` の `AdVideoBase` / `Clip` / `animC` / `telopBase` / `wrapperBase` を import する** — 自前で OffthreadVideo を書かない
5. **calcFontSize は使わない** — フォントサイズは下記表から手動で選ぶ（shared.tsx は自動縮小を持っていない）

---

### Step 1: 前提情報の読み込み

以下を Read:

- `作業中動画/プロンプト.md` — 構成案・シーン数・秒数・役割
- `src/compositions/shared.tsx` — `telopBase` / `wrapperBase` / `Clip` 型の最新シグネチャを確認
- `.claude/skills/telop-design/patterns.md` — bs スタイルに近いパターンを特定するため（参照のみ）

bs 分析結果（制作フロー Step 2 で実行済み・会話コンテキスト上にある）から以下を抽出:

- **各シーンの文言（原文）** — 丸コピー
- **各シーンの durationInFrames** — 秒数 × 30
- **各シーンの配置** — 上/中/下（`wrapperBase(y)` の y 値 0.0〜1.0 に変換）
- **各シーンのフォントサイズ** — bs 抽出値 or 下記の文字数表から選択
- **各シーンのアニメーション** — 基本は `animC`（タイプライター式 blurフェードイン）

---

### Step 2: フォントサイズの決定

`telopBase(fontSize, borderWidth)` に渡す数値を手動で決める:

| 文字数 | 推奨 fontSize | borderWidth |
|--------|-------------|-------------|
| 1-4字  | 140-180     | 6-8         |
| 5-8字  | 100-140     | 5-6         |
| 9-12字 | 80-100      | 4-5         |
| 13-18字 | 60-80      | 4           |
| 19字以上 | 48-60 (2行分割検討) | 3-4 |

bs 抽出のサイズが上記と大きくズレている場合は bs を優先する（バズ動画のスタイルが正解）。

---

### Step 3: y 位置の決定

`wrapperBase(y)` の y は画面縦位置を 0-1 で指定する:

- `0.1` — 画面上部
- `0.5` — 画面中央
- `0.78〜0.85` — 画面下部（一般的な位置）

bs のテロップが画面の縦方向にどこにあったかを見て決める。

---

### Step 4: AdVideo.tsx 上書き

Bash ヒアドキュメントで AdVideo.tsx を完全に書き直す:

```bash
cat <<'EOF' > /Users/keeee/Desktop/Dev/OssMovieAIz/src/compositions/AdVideo.tsx
import React from "react";
import { AdVideoBase, animC, Clip, telopBase, wrapperBase } from "./shared";

// ===== bsベースライン文言（Step 8 で新テーマに書き換える） =====
const C1_TEXT = "bs原文1";
const C2_TEXT = "bs原文2";
// ... 必要なだけ

const clips: Clip[] = [
  {
    file: "",  // ← Step 8 Phase B で実ファイル名に差し替える
    durationInFrames: 75,
    render: (frame) => (
      <div style={wrapperBase(0.85)}>
        <div style={telopBase(120, 5)}>{animC(frame, C1_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "",
    durationInFrames: 90,
    render: (frame) => (
      <div style={wrapperBase(0.78)}>
        <div style={telopBase(100, 5)}>{animC(frame, C2_TEXT, 3)}</div>
      </div>
    ),
  },
  // ... 他のシーンも同様
];

export const AdVideo: React.FC = () => (
  <AdVideoBase clips={clips} />
);

export const adVideoClips = clips;
EOF
```

**注意**:
- `AdVideoBase` に `bgm` / `narration` を渡さない（まだ音声ファイルも無い）。Step 9 の `/video-script` 完了後に Step 8 Phase B で追加する
- `Clip` 型は `{ file: string; durationInFrames: number; render: (frame) => ReactNode }` なので、`main`/`sub` プロパティは使わない
- 複数要素（上テキスト + 下テキスト等）が必要な場合は `render` 関数内で `<>` で複数の div を返す

---

### Step 5: 黒背景で Remotion 確認

```bash
cd /Users/keeee/Desktop/Dev/OssMovieAIz
npm run studio
```

起動後、ユーザーに確認を依頼:

```
http://localhost:3000 を開いて、bsベースラインのテロップが意図通り流れているか確認してください。
- 黒背景の上にテロップだけが流れる状態です
- 文言は bs 原文のまま（新テーマへの書き換えは Step 8 で行います）
- スタイル・配置・サイズが bs 分析結果と一致しているか確認

問題なければ「はい」と言ってください。修正が必要なら具体的に指摘してください。
```

**必ずユーザー承認を待つ**。承認されるまで Step 6 以降には進まない。

---

### Step 6: 完了報告

```
✅ bsベースラインのテロップ実装完了
- Scene数: X
- 合計尺: XX秒（XXXフレーム）
- 各シーンのスタイル: bs抽出値そのまま

次のステップ:
- Step 6: /flux-image で各シーンの静止画を生成
- Step 7: /wan-video でクリップを生成（run_in_background: true で背景実行）
- Step 8a: Wan 生成中に /telop-design Phase A（文言書き換え）を並行実施
```

---

### 注意点

- **bs 分析結果がない場合**: 「先に bs 分析（Step 2）を実行してください」と伝えて終了
- **プロンプト.md がない場合**: 「先に /plan-video（Step 4）を実行してください」と伝えて終了
- **前回の AdVideo.tsx が残っている場合**: 気にせずヒアドキュメントで上書きする（Step -1 の `bash scripts/reset_project.sh` で初期化済みの前提だが、忘れていても問題なし）
- **縦書き / 横書き**: bs が縦書きなら `telopBase` に `writingMode: "vertical-rl"` を上書きする必要がある。shared.tsx の `telopBase` はデフォルト横書きなので、縦書き bs の場合は render 関数内で追加スタイルをマージ:
  ```tsx
  <div style={{...telopBase(120, 5), writingMode: "vertical-rl"}}>
  ```
- **原文が長すぎて縦で収まらない場合**: この時点では実映像がないので調整不要。Step 8 の `/telop-design` で実映像を見てから最終調整する

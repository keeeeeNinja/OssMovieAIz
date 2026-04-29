---
name: telop-baseline
description: bs_composition.json のテロップスタイル（配置・色・フォント・サイズ・原文 telop.text）を、AdVideo.tsx に B+共通アーキテクチャでベタ書き実装する。制作フローのStep 5で必ず使う。映像クリップが未完成の状態で動くので、clip.file は空文字のまま。「bsベースライン実装」「Step 5」「黒背景のテロップ確認」という場面で使う。
allowed-tools: Read, Bash(cat *), Bash(ls *), Bash(npm *), Bash(mkdir *), Grep, Glob
---

## bsテロップベースライン実装スキル

制作フローのStep 5として発動する。`bs_composition.json` から各カットのテロップ情報を取り出し、その値をそのまま AdVideo.tsx にベタ書きで実装する。文言書き換えは Step 8 の `/telop-design` 担当なので、このスキルでは **`telop.text` 原文をそのまま**書き出す。

---

### 絶対ルール

1. **入力は `作業中動画/bs_composition.json` のみ。AdVideo.tsx を Read しない**
   - 前回の動画コードに引きずられる事故を防ぐための強制ルール
   - JSON にある値だけを根拠に書き出す
2. **clip.file は必ず空文字 `""`** — クリップはまだ生成されていない。`shared.tsx` の `AdVideoBase` は `clip.file` が空文字のとき `OffthreadVideo` をスキップして黒背景＋テロップだけ描画する
3. **`bs_composition.json` の `telop.text` 原文をそのまま使う** — 文言書き換えは Step 8 の責務。ここでは絶対に書き換えない
4. **Bash ヒアドキュメントで AdVideo.tsx を上書きする** — Write ツールは使わない。前回の AdVideo.tsx を参照しないための強制リセット
5. **B+共通アーキテクチャ**: `shared.tsx` から `AdVideoBase` / `animC` / `Clip` 型だけを import し、テロップ表現は各シーンの `render` 関数内に**ベタ書き**する。`telopBase` `wrapperBase` は呼ばない（色固定の制約を避けるため）

---

### Step 1: 入力 JSON を読む

```bash
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/bs_composition.json
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/プロンプト.md
```

両方が存在することを確認。どちらか欠けていれば：
- `bs_composition.json` がない → 「先に bs 分析（Step 2）を実行して JSON を保存してください」
- `プロンプト.md` がない → 「先に `/plan-video`（Step 4）を実行してください」

両方あれば Read で読み込む。**AdVideo.tsx は絶対に Read しない**。

---

### Step 2: bs JSON のテロップ情報を抽出する

`bs_composition.json` の `cuts[]` を順に処理する。各カットから以下を取り出す：

| JSON のキー | 用途 |
|------------|------|
| `cuts[i].duration_frames` | `clip.durationInFrames` にそのまま |
| `cuts[i].telop.text` | `animC` に渡す原文文言 |
| `cuts[i].telop.size_ratio` | フォントサイズ計算 |
| `cuts[i].telop.font_type` | fontFamily / fontWeight 決定 |
| `cuts[i].telop.position.x` `.y` | 配置決定 |
| `cuts[i].telop.original_color` | `color` |
| `cuts[i].telop.border` | 縁取り（null なら無し） |
| `cuts[i].telop.shadow` | 影（null なら無し） |
| `cuts[i].telop.timing.start` | `animC` 開始フレーム（秒×30） |

`telop` が `null` のカットはテロップ無し。`render` 関数で空 `<></>` を返す。

---

### Step 3: JSON → AdVideo.tsx 変換ルール

縦型 1080×1920 を前提に変換する（Composition の `height: 1920` をそのまま掛ける）。

| bs JSON | AdVideo.tsx |
|---------|------------|
| `size_ratio: 0.08` | `fontSize: Math.round(0.08 * 1920) = 154` |
| `font_type: "gothic_bold"` | `fontFamily: '"Noto Sans JP", "Hiragino Sans", sans-serif'`, `fontWeight: 900` |
| `font_type: "mincho"` | `fontFamily: '"Hiragino Mincho ProN", "YuMincho", serif'`, `fontWeight: 600` |
| `position.y < 0.3` | `<AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: y*1920 }}>` |
| `position.y` 0.3〜0.7 | `<AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>` |
| `position.y > 0.7` | `<AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: (1-y)*1920 }}>` |
| `original_color: "#FFFFFF"` | `color: "#FFFFFF"` |
| `border: { color: "#000", width: 4 }` | `WebkitTextStroke: "4px #000"`, `paintOrder: "stroke fill"` |
| `border: null` | （何もつけない） |
| `shadow: { color: "rgba(0,0,0,0.5)", blur: 8 }` | `textShadow: "0 0 8px rgba(0,0,0,0.5)"` |
| `shadow: null` | （何もつけない） |
| `timing.start: 0.3` | `animC(frame, text, Math.round(0.3 * 30))` = `animC(frame, text, 9)` |

`textAlign: "center"` は常に付ける（`position.x` は中央が大半なので）。`x` が 0.3 未満や 0.7 超なら `alignItems` を `flex-start` / `flex-end` に変える。

---

### Step 4: AdVideo.tsx を Bash ヒアドキュメントで上書き

JSON のカット数だけ clip エントリを生成する。以下が**B+共通**のテンプレート骨格：

```bash
cat <<'EOF' > /Users/keeee/Desktop/Dev/OssMovieAIz/src/compositions/AdVideo.tsx
import React from "react";
import { AbsoluteFill } from "remotion";
import { AdVideoBase, animC, Clip } from "./shared";

const clips: Clip[] = [
  // === C1（bs JSON cuts[0] から生成）===
  {
    file: "",  // Step 8 Phase B で実ファイル名に差し替え
    durationInFrames: 36,  // ← cuts[0].duration_frames
    render: (frame) => (
      <AbsoluteFill style={{
        justifyContent: "flex-start",
        alignItems: "center",
        paddingTop: 230,  // ← position.y=0.12 × 1920 ≒ 230
      }}>
        <div style={{
          fontFamily: '"Noto Sans JP", "Hiragino Sans", sans-serif',
          fontWeight: 900,
          fontSize: 154,  // ← size_ratio=0.08 × 1920 ≒ 154
          color: "#000000",  // ← original_color
          textAlign: "center",
          WebkitTextStroke: "2px #FFFFFF",  // ← border.width + border.color
          paintOrder: "stroke fill",
        }}>
          {animC(frame, "驚愕！", 9)}  {/* telop.text と timing.start*30 */}
        </div>
      </AbsoluteFill>
    ),
  },
  // === C2 ===
  // （省略：JSON の cuts[1] から同様に生成）
];

export const AdVideo = () => (
  <AdVideoBase clips={clips} />
);

export const adVideoClips = clips;
EOF
```

#### `telop` が null のカット
```tsx
{
  file: "",
  durationInFrames: 60,
  render: () => <></>,  // テロップ無し
},
```

#### 縦書きが必要な場合
bs に縦書き専用フィールドはないが、`font_type` が縦組み系なら render 内で `writingMode: "vertical-rl"` を付ける：
```tsx
<div style={{
  ...,
  writingMode: "vertical-rl",
}}>
```

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
- 文言は telop.text 原文のまま（新テーマへの書き換えは Step 8 で行います）
- スタイル・配置・サイズが bs_composition.json の値と一致しているか確認

問題なければ「はい」と言ってください。修正が必要なら具体的に指摘してください。
```

**必ずユーザー承認を待つ**。承認されるまで Step 6 以降には進まない。

---

### Step 6: 完了報告

```
✅ bsベースラインのテロップ実装完了
- Scene数: X
- 合計尺: XX秒（XXXフレーム）
- 各シーンのスタイル: bs_composition.json の値そのまま反映

次のステップ:
- Step 6: /flux-image で各シーンの静止画を生成
- Step 7: /wan-video でクリップを生成（run_in_background: true で背景実行）
- Step 8a: Wan 生成中に /telop-design Phase A（文言書き換え）を並行実施
```

---

### 注意点

- **bs_composition.json がない場合**: 「先に bs 分析（Step 2）を実行して JSON を保存してください」と伝えて終了
- **プロンプト.md がない場合**: 「先に `/plan-video`（Step 4）を実行してください」と伝えて終了
- **AdVideo.tsx を読みたくなったら止まる**: 入力は JSON だけ。AdVideo.tsx の現状は知る必要がない
- **shared.tsx の `animC`** は CHARS_DURATION=10, FADE_FRAMES=12（短いクリップでも文字が見える設定）。長いクリップで遅く見せたい場合は `animC` の第3引数の startFrame で調整する（中身を変えない）
- **Composition の解像度ズレに注意**: `Root.tsx` が `width: 1920, height: 1080`（横型）になっている場合、size_ratio の掛け算は `× 1080` に変える。CLAUDE.md の縦型 1080×1920 が正の場合は `× 1920`。Root.tsx を必ず確認してから変換する

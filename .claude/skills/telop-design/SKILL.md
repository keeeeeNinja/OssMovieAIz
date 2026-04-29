---
name: telop-design
description: bs_composition.json をベースに、bsスタイルを引き継ぎつつ実映像に合わない部分だけ差分調整。テロップ文言は telop.text の文字数・役割を維持して新テーマに書き換える。AdVideo.tsx を Read せず、JSON から再構築する。
allowed-tools: Bash(ffmpeg *), Bash(ffprobe *), Bash(ls *), Bash(curl *), Bash(mkdir *), Bash(python3 *), Bash(npx *), Bash(cat *), Bash(cp *), Read, WebFetch
---

## テロップ最適化・文言作成・実装（B+共通アーキテクチャ）

Step 8 として発動するスキル。**`bs_composition.json` を真実の出典**として、bs スタイルをそのまま使い、文言だけ新テーマに合わせて書き換える。実映像との相性で問題があるシーンだけ差分調整する。

### 実行モード

Wan 生成は `run_in_background` で長時間走るので、メイン会話はその間に Step 8 の一部を先行実装する。このスキルは2段階に分けて呼び出す:

- **Phase A — text-only モード（Step 7 と並行）**: クリップがまだ無い状態で、**Step 1〜2（JSON 読み込み + 文言書き換え）と Step 5（AdVideo.tsx 上書き）だけ**を実行する。Step 3〜4（フレーム抽出・映像相性チェック）と Step 6（Remotion still レビュー）はスキップ。`clip.file` は空文字のまま残す
- **Phase B — style tuning モード（Step 7 完了後）**: クリップを `public/` に配置 → AdVideo.tsx の `file` を実ファイル名に差し替え → Step 3〜4（フレーム抽出・相性チェック）→ 問題があれば Step 5 でスタイル微調整して再上書き → Step 6（Remotion still レビュー）

ユーザーから `/telop-design` と呼ばれたら、まず以下のコマンドで Phase 判定:

```bash
ls /Users/keeee/Desktop/Dev/OssMovieAIz/public/scene_*.mp4 2>/dev/null | wc -l
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/theme*/scene_*.mp4 2>/dev/null | wc -l
```

- どちらも `0` → **Phase A**
- `作業中動画/theme*/` には揃っているが `public/` に未コピー → **Phase B 冒頭で `cp` してから進める**
- `public/` に揃っている → **Phase B**

---

### 絶対ルール（最重要）

1. **入力は `作業中動画/bs_composition.json` と `作業中動画/プロンプト.md` のみ。AdVideo.tsx を Read しない**
   - Phase B でも Read しない。スタイル相性の調整は「実映像 vs bs JSON」で判断する
   - 前回の動画コードに引きずられる事故を防ぐための強制ルール
2. **テロップ文言は `telop.text` の文字数帯・役割を維持する**。短いキャッチコピーを長い説明文に膨らませない
3. **bs スタイルが「デフォルト正解」**。全部捨てて作り直さない。実映像に合わない部分だけ直す
4. **Bash ヒアドキュメントで AdVideo.tsx を上書きする** — Write ツールは使わない。前回のコードを読まないための強制リセット
5. **B+共通アーキテクチャ**: `shared.tsx` から `AdVideoBase` / `animC` / `Clip` 型だけを import し、テロップ表現は各シーンの `render` 関数内に**ベタ書き**する
6. **アニメーションは全シーン `animC`**（`shared.tsx` の `animC` をそのまま使う。再定義しない）

---

### Step 1: 入力 JSON とプロンプト.md を読む

```bash
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/bs_composition.json
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/プロンプト.md
```

両方 Read する。**AdVideo.tsx は Read しない**（Phase A・B 共通）。

`bs_composition.json` から以下を抽出:
- 各カットの `telop.text`（原文文言・**書き換え前**）
- 各カットの `telop.role` / `size_ratio` / `position` / `font_type` / `original_color` / `border` / `shadow` / `timing`
- 各カットの `duration_frames`

`プロンプト.md` からテーマ情報を抽出。

---

### Step 2: テロップ文言の書き換え

`telop.text` の文字数と役割を維持して、新テーマに合わせた文言を作る。

#### 文字数維持ルール

| 原文 (`telop.text`) の文字数 | 役割 | 新テキストの制約 |
|--------|------|---------------|
| 1-4文字 | キャッチコピー | 同じ1-4文字で作る。説明しない |
| 5-8文字 | 短文コピー | 同じ5-8文字。情報を詰め込まない |
| 9-12文字 | 中文コピー | 同じ9-12文字 |
| 13文字以上 | 説明文 | 同等の文字数 |

#### シーン尺との整合

| シーンの尺（`duration_frames` ÷ 30） | テロップ最大文字数の目安 |
|------|-------------------|
| 3秒以下（90f以下） | 5文字 |
| 4-5秒（120-150f） | 10文字 |
| 6秒以上（180f以上） | 制限なし |

#### 文言提案フォーマット

```
Scene 1（フック・3文字 / cut.role: hook）: 原文「衝撃！」→ 新「驚愕！」
Scene 2（本題・8文字 / cut.role: main）: 原文「これが噂の新技術」→ 新「まつ毛が生まれ変わる」
Scene 3（CTA・5文字 / cut.role: cta）: 原文「今すぐ予約」→ 新「無料で体験」
```

ユーザーに承認をもらってから Step 3 へ。

> **Phase A ではここから Step 5 に飛ぶ**（フレーム抽出・相性チェックは Phase B のみ）

---

### Step 3: 映像フレームの分析（Phase B 専用）

#### 3-1. クリップを public/ に揃える

```bash
ls /Users/keeee/Desktop/Dev/OssMovieAIz/public/scene_*.mp4 2>/dev/null
```

無ければ `作業中動画/theme*/scene_*.mp4` から `cp`:
```bash
cp /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/theme1/scene_*.mp4 /Users/keeee/Desktop/Dev/OssMovieAIz/public/
```

#### 3-2. フレーム抽出

```bash
mkdir -p /tmp/telop-design-frames
ffmpeg -i "/Users/keeee/Desktop/Dev/OssMovieAIz/public/scene_T1_C01_wan21.mp4" \
  -vf "fps=1/2,scale=540:-1" /tmp/telop-design-frames/C01-%03d.jpg -y 2>/dev/null
```

各クリップで実行する。

#### 3-3. 各クリップの映像特徴を Read で確認

| 分析項目 | 見るべきこと |
|---------|------------|
| **明暗** | 暗い/明るい/コントラスト強/淡い |
| **被写体位置** | 中央/上部/下部/左右 |
| **空きスペース** | テロップを置ける余地はどこか |
| **bs スタイルとの相性** | `position` `original_color` がそのまま使えるか |

---

### Step 4: bs スタイルと実映像の相性チェック（Phase B 専用）

各シーンについて、bs JSON のスタイルと実映像を照合する。

| チェック項目 | 判定基準 | 問題があれば |
|------------|---------|------------|
| **被写体との重なり** | 端がかすめる程度は OK。顔・目・口・商品の中心部分に文字が乗ったら NG | `position.y` を上下に振るか、`alignItems` を変更 |
| **コントラスト** | 背景とテキスト色が同化していなければ OK | `border` を追加 / 強化、または `shadow` を追加 |
| **空きスペース** | bs の配置位置に実映像で空きがあるか | 空いている場所へ移動 |
| **雰囲気の一致** | **チェックしない。bs の `font_type` `original_color` `border` はそのまま引き継ぐ** | ユーザー明示指示があった場合のみ変更 |

**判定結果は3段階:**
- **OK** — bs スタイルそのまま → 変更なし
- **微調整** — `position.y` の値だけ変える、`border` の幅を増やす程度
- **大幅変更** — レイアウトそのものを変える（例: 上配置→下配置）。ユーザーに必ず報告

---

### Step 5: AdVideo.tsx を Bash ヒアドキュメントで上書き

**Phase A も Phase B もここで AdVideo.tsx を**書き直す**（Phase B はクリップファイル名と Step 4 の調整値を反映）。

#### JSON → AdVideo.tsx 変換ルール（再掲）

縦型 1080×1920 を前提に変換する。`Root.tsx` の `height` を必ず確認してから掛ける。

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
| `shadow: { color, blur }` | `textShadow: "0 0 ${blur}px ${color}"` |
| `timing.start: 0.3` | `animC(frame, text, 9)`（第3引数 = `Math.round(timing.start * 30)`） |

#### テンプレート（B+共通）

```bash
cat <<'EOF' > /Users/keeee/Desktop/Dev/OssMovieAIz/src/compositions/AdVideo.tsx
import React from "react";
import { AbsoluteFill } from "remotion";
import { AdVideoBase, animC, Clip } from "./shared";

const clips: Clip[] = [
  // === C1 ===
  {
    file: "scene_T1_C01_wan21.mp4",  // Phase A は ""、Phase B は実ファイル名
    durationInFrames: 75,  // ← cuts[0].duration_frames
    render: (frame) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 290,  // ← (1 - 0.85) * 1920 ≒ 290
      }}>
        <div style={{
          fontFamily: '"Noto Sans JP", "Hiragino Sans", sans-serif',
          fontWeight: 900,
          fontSize: 154,
          color: "#FFFFFF",
          textAlign: "center",
          WebkitTextStroke: "5px #000000",
          paintOrder: "stroke fill",
          textShadow: "0 0 8px rgba(0,0,0,0.4)",
        }}>
          {animC(frame, "驚愕！", 9)}
        </div>
      </AbsoluteFill>
    ),
  },
  // === C2 ===
  // （省略：bs JSON cuts[1] から同様に生成）
];

export const AdVideo = () => (
  <AdVideoBase
    clips={clips}
    bgm="bgm.mp3"
    narration="narration.wav"
  />
);

export const adVideoClips = clips;
EOF
```

**Phase A の場合**:
- 各 `clip.file` は `""` のまま
- `bgm` `narration` 引数は省略（音声ファイル未生成）→ `<AdVideoBase clips={clips} />`

**Phase B の場合**:
- `clip.file` を実ファイル名に
- `bgm` `narration` がすでに生成済みなら指定（Step 9 完了後）。Step 9 が未完了なら省略のまま

#### `telop` が null のカット
```tsx
{
  file: "scene_T1_C03_wan21.mp4",
  durationInFrames: 90,
  render: () => <></>,  // テロップ無し
},
```

#### 複雑レイアウト（複数テキスト要素）
1 シーンに複数のテキスト要素が必要なら、`render` 内で複数 div を配置する：

```tsx
render: (frame) => (
  <AbsoluteFill style={{ justifyContent: "space-between", padding: "240px 60px" }}>
    <div style={{ alignSelf: "flex-end", fontSize: 100, fontFamily: "Georgia, serif", color: "#1A1A1A" }}>
      {animC(frame, "BEAUTY")}
    </div>
    <div style={{ alignSelf: "flex-start", fontSize: 60, color: "#555555" }}>
      {animC(frame, "美しさの新基準", 30)}
    </div>
  </AbsoluteFill>
),
```

`animC` の第3引数（startFrame）をずらすと時差出現が作れる。

---

### Step 6: Remotion still で確認（Phase B 専用）

各クリップの中間フレームを書き出して読み込み、被写体との重なり・コントラストを目視確認。

```bash
cd /Users/keeee/Desktop/Dev/OssMovieAIz
# 各クリップの中間フレームを計算（duration_frames の半分 + 累積開始位置）
npx remotion still src/index.ts AdVideo /tmp/telop-still-C01.png --frame=37
npx remotion still src/index.ts AdVideo /tmp/telop-still-C02.png --frame=120
# ...
```

書き出した PNG を Read で読み込み、以下を確認:
- 被写体との重なり / コントラスト / サイズ感 / 可読性

ズレがあれば Step 5 に戻って調整値を変えて再上書き。

---

### Step 7: 完了報告

```
✅ テロップ最適化完了（Phase {A|B}）
- Scene数: X
- 文言書き換え: 原文文字数を維持
- スタイル変更: N/X シーン（残りは bs JSON のままそのまま反映）
- 入力: 作業中動画/bs_composition.json + プロンプト.md
- 出力: src/compositions/AdVideo.tsx

Remotion Studio で動きを確認してください: http://localhost:3000
```

---

### 注意点

- **AdVideo.tsx を読みたくなったら止まる**: 入力は JSON だけ。前回コードを参考にする運用は事故の元
- **shared.tsx の `animC`** は CHARS_DURATION=10, FADE_FRAMES=12（短いクリップでも文字が見える）。ここで再定義しない
- **`Root.tsx` の解像度**: 縦型 1080×1920 を前提に書いてあるが、実プロジェクトは `width: 1920, height: 1080` になっている可能性あり。Step 5 の `* 1920` は `Root.tsx` の `height` 値に合わせて変える
- **音量デフォルト**: `AdVideoBase` のデフォルトは `narrationVolume=0.4` `bgmVolume=0.35`。明示的に変えたい場合だけ引数で指定する

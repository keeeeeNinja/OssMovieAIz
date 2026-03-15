---
name: telop-design
description: 作業中動画のクリップを分析し、bannnner.comのバナーデザインパターンを参考にして最適なテロップデザインをAdVideo.tsxに実装する。テロップのデザインや配置を変えたい、バナーを参考にしたい、動画のテキストスタイルを改善したい、という場面で必ず使う。毎回「ショート動画のプロ一覧」に頼るのではなく、実際のバナー画像から帰納的にデザインを導くことが目的。
allowed-tools: Bash(ffmpeg *), Bash(ffprobe *), Bash(ls *), Bash(curl *), Bash(mkdir *), Bash(python3 *), Bash(npx *), Read, Write, WebFetch
---

## テロップデザイン設計・実装

各クリップの映像内容をパターン辞書と照合し、その動画に固有のテロップデザインをAdVideo.tsxに実装する。

### 絶対ルール（最重要）

1. **AdVideo.tsxの既存コードを読まない。** 前回のスタイルが目に入ること自体が引きずりの原因。実装時は既存コードを参照せず、テンプレートから書き直す。**WriteツールはReadが必須なので使わない。必ずBashのヒアドキュメントで上書きする：`bash cat <<'EOF' > /Users/keeee/Desktop/Dev/OssMovieAIz/src/compositions/AdVideo.tsx ... EOF`**
2. **パターン辞書から選ぶ。** bannnner.comを毎回収集しない。まず patterns.md の10パターンを参照し、マッチするパターンを選ぶ。辞書に合うものがなければ新規収集する。
3. **各シーンに異なるパターンを使う。** 3シーンで同じパターン・同じフォントwightを使わない。
4. **自分でパターンを選んでユーザーに提案する。** ユーザーに選ばせない。私が映像を分析してベストなパターンを判断し、理由を添えて提案する。
5. **フォントサイズは64px未満にしない。** 動画は5秒で消える。小さいと読めない。
6. **アニメーションは全シーン共通で「もわっとフェードイン」を使う。** テキスト配置はパターン辞書と映像に応じて判断する。

---

### デフォルトアニメーション標準（全シーン共通）

**全シーン必ずこのアニメーションを使う。** 文字がタイプライター式に順番に現れ、blurが溶けながら40フレームかけてフェードイン。実装はファイル冒頭に共通関数 `animC` を定義して全シーンで呼び出す。

```tsx
// ファイル冒頭に定義（clips配列の外）
const animC = (frame: number, text: string, startFrame = 20) => {
  const CHARS_DURATION = 30;
  const FADE_FRAMES = 40;
  const charsPerFrame = text.length / CHARS_DURATION;
  return text.split("").map((char, i) => {
    const charAppearFrame = startFrame + Math.floor(i / charsPerFrame);
    const age = frame - charAppearFrame;
    if (age < 0) return null;
    const t = Math.min(1, age / FADE_FRAMES);
    return (
      <span key={i} style={{
        opacity: t,
        filter: `blur(${(1 - t) * 24}px)`,
      }}>{char}</span>
    );
  });
};

// 各シーンのrender関数内で呼び出す
render: (frame: number) => (
  <AbsoluteFill style={{ /* パターンに応じた配置スタイル */ }}>
    <div style={{ /* パターンに応じたテキストスタイル */ }}>
      {animC(frame, "テロップ文言")}
    </div>
  </AbsoluteFill>
)
```

**複数テキスト要素（P7など）では `startFrame` をずらして時差を付ける:**
```tsx
{animC(frame, "SILKY TEXTURE")}       // startFrame=20（デフォルト）
{animC(frame, "とろける塗り心地", 30)} // startFrame=30（少し遅れて出現）
```

---

### Step 1: パターン辞書と原則を読み込む

以下を必ず読む：

```
Read: /Users/keeee/Desktop/Dev/OssMovieAIz/skills/telop-design/patterns.md
Read: /Users/keeee/Desktop/Dev/OssMovieAIz/skills/telop-design/matching-rules.md
Read: /Users/keeee/Desktop/Dev/OssMovieAIz/skills/telop-design/fonts-colors-decorations.md
Read: /Users/keeee/Desktop/Dev/OssMovieAIz/デザインの極意書.md
```

これで10パターンのCSS実装例・使いどころ・映像→パターンの判定ルールが頭に入る。

---

### Step 2: 動画クリップの分析

#### 2-1. ファイルと尺を確認する

```bash
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/*.mp4
```

使用するクリップ（scene1〜など）とそのdurationInFrames（fps30換算）を確認する。
performing_a_facial.mp4 など参照動画素材は除外する。

#### 2-2. フレーム抽出（クリップごと）

```bash
mkdir -p /tmp/telop-design-frames
ffmpeg -i "VIDEO_PATH" -vf "fps=1/5,scale=640:-1" /tmp/telop-design-frames/CLIP_NAME-%03d.jpg -y 2>/dev/null
```

#### 2-3. 各クリップの映像特徴を分析する

| 分析項目 | 見るべきこと |
|---------|------------|
| **明暗** | 暗い/明るい/コントラスト強/淡い |
| **被写体位置** | 中央/上部/下部/左右 |
| **空きスペース** | テロップを置ける余地はどこか |
| **雰囲気** | 高級/カジュアル/シネマ/清潔/和風 など |
| **シーン役割** | フック/本題/行動喚起 |

---

### Step 3: パターンを選択する

Step 1で読んだ `matching-rules.md` の判定フローに従い、各クリップのパターンを決定する。

**判定フロー（4段階）:**
1. 明暗 → テキスト色を決める
2. 被写体位置 → テロップの配置エリアを決める
3. 空きスペース → 配置を確定する
4. 雰囲気 × シーン役割 → パターンを決定する

**3シーンの組み合わせ制約:**
- 同じパターンを2回使わない
- フック（1枚目）は P1, P3, P6 のいずれか（インパクト重視）
- フォントwightを3シーンで変化させる（例: 800 → 300 → 600）
- matching-rules.md の「組み合わせ例」を参考にする

**パターンが辞書に合わない場合のみ** bannnner.comで新しいバナーを収集する:
```
WebFetch: https://bannnner.com/tag/[ジャンル]/
→ 画像URLを抽出 → curl でダウンロード → Read で分析
```

---

### Step 4: テロップデザイン提案

各シーンについて以下を提案する。ユーザーに選ばせず、**自分が判断して提案する**。

```
【scene1_XXX — フック】
適用パターン: P3 上部大文字ヘッドライン
理由: [映像特徴から判断した理由を1行で]
- 配置: 上部左寄せ
- フォント: 超太ゴシック (weight 900)
- サイズ: 96px
- 色: #FFFFFF
- 装飾: テキストシャドウ
- アニメーション: A（ゆっくりフェードイン 90フレーム）

【scene2_XXX — 本題】
適用パターン: P4 縦書き端配置
...

【scene3_XXX — 行動喚起】
適用パターン: P5 左上ミニマル
...
```

ユーザーに確認：「この方向性でよければ実装します。」

---

### Step 5: AdVideo.tsxを実装する

**AdVideo.tsxは読まずに書き直す。** 前回のコードは参照しない。

以下のテンプレートに、Step 4で決めたスタイルを**インラインで**書き込む。

#### デフォルトスタイル（特別な理由がない限りここから始める）

| 項目 | デフォルト値 |
|-----|------------|
| アニメーション | `animC`（タイプライター式 + blurフェードイン） |
| フォント | `Hiragino Mincho ProN, YuMincho, serif` |
| fontWeight | `300` |
| fontSize | `92px` |
| letterSpacing | `0.25em`（1行に収まらない場合は `0.05em` まで縮める） |
| 色 | `#FFFFFF` |
| textShadow | `0 2px 20px rgba(0,0,0,0.5)` |
| 配置 | 映像の空きスペースに合わせて判断（下部中央が多い） |

フォント・色・サイズ・配置は映像と案件の雰囲気に応じて変える。animCは全シーン固定。

#### テンプレート構造（必ずこの構造で書く）

```tsx
import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

// ===== デフォルトアニメーション（全シーン共通） =====
const animC = (frame: number, text: string, startFrame = 20) => {
  const CHARS_DURATION = 30;
  const FADE_FRAMES = 40;
  const charsPerFrame = text.length / CHARS_DURATION;
  return text.split("").map((char, i) => {
    const charAppearFrame = startFrame + Math.floor(i / charsPerFrame);
    const age = frame - charAppearFrame;
    if (age < 0) return null;
    const t = Math.min(1, age / FADE_FRAMES);
    return (
      <span key={i} style={{ opacity: t, filter: `blur(${(1 - t) * 24}px)` }}>{char}</span>
    );
  });
};

// ===== クリップ定義 =====
const clips = [
  {
    file: "CLIP_FILE_1.mp4",
    durationInFrames: 150,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-start",
        alignItems: "flex-start",
        paddingTop: 160,
        paddingLeft: 48,
      }}>
        <div style={{
          fontSize: 92,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.05em",
          color: "#FFFFFF",
          textShadow: "0 2px 20px rgba(0,0,0,0.5)",
        }}>
          {animC(frame, "テロップ1")}
        </div>
      </AbsoluteFill>
    ),
  },
  {
    file: "CLIP_FILE_2.mp4",
    durationInFrames: 150,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 180,
      }}>
        <div style={{
          fontSize: 92,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.25em",
          color: "#FFFFFF",
          textShadow: "0 2px 20px rgba(0,0,0,0.5)",
        }}>
          {animC(frame, "テロップ2")}
        </div>
      </AbsoluteFill>
    ),
  },
  {
    file: "CLIP_FILE_3.mp4",
    durationInFrames: 150,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "center",
        alignItems: "center",
      }}>
        <div style={{
          fontSize: 92,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.25em",
          color: "#FFFFFF",
          textShadow: "0 2px 20px rgba(0,0,0,0.5)",
        }}>
          {animC(frame, "テロップ3")}
        </div>
      </AbsoluteFill>
    ),
  },
];

// ===== Telopコンポーネント =====
const Telop: React.FC<(typeof clips)[number]> = (clip) => {
  const frame = useCurrentFrame();
  if (clip.render) return clip.render(frame);
  return null;
};

// ===== トランジション（白フラッシュ）=====
const FLASH_FRAMES = 8;
const WhiteFlash: React.FC = () => {
  const frame = useCurrentFrame();
  const transitions: number[] = [];
  let acc = 0;
  for (let i = 0; i < clips.length - 1; i++) {
    acc += clips[i].durationInFrames;
    transitions.push(acc);
  }
  const opacity = transitions.reduce((o, t) => {
    const dist = Math.abs(frame - t);
    if (dist > FLASH_FRAMES) return o;
    return Math.max(o, interpolate(dist, [0, FLASH_FRAMES], [0.8, 0], { extrapolateRight: "clamp" }));
  }, 0);
  if (opacity === 0) return null;
  return <AbsoluteFill style={{ backgroundColor: `rgba(255,255,255,${opacity})`, zIndex: 10 }} />;
};

// ===== メインコンポーネント =====
export const AdVideo: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Audio src={staticFile("bgm.mp3")} volume={0.35} />
      <Audio src={staticFile("narration.wav")} volume={0.5} />
      {clips.map((clip) => {
        const start = from;
        from += clip.durationInFrames;
        return (
          <Sequence key={clip.file} from={start} durationInFrames={clip.durationInFrames}>
            <AbsoluteFill>
              <OffthreadVideo
                src={staticFile(clip.file)}
                style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center center" }}
              />
              <Telop {...clip} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <WhiteFlash />
    </AbsoluteFill>
  );
};
```

各クリップの `render` 関数内のスタイルをStep 4で決めた値に書き換える。配置・フォント・色はシーンごとに変えてよい。animCは変えない。

#### P6・P7・P8を使う場合

P6・P7・P8は複数要素や帯構造が必要。clips配列には残したまま、`render` 関数でカスタム描画する。

**P6（中央インパクト数字）— メイン＋サブの2要素:**
```tsx
{
  file: "CLIP_FILE.mp4",
  durationInFrames: 150,
  render: (frame: number) => (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ textAlign: "center", opacity: interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" }) }}>
        <div style={{ fontSize: 140, fontWeight: 900, color: "#E53935" }}>50%OFF</div>
        <div style={{ fontSize: 36, fontWeight: 400, color: "#FFFFFF", marginTop: 8 }}>期間限定</div>
      </div>
    </AbsoluteFill>
  ),
},
```

**P7（英字+日本語二層）— 対角線に2要素:**
```tsx
{
  file: "CLIP_FILE.mp4",
  durationInFrames: 150,
  render: (frame: number) => {
    const opacity = interpolate(frame, [0, 25], [0, 1], { extrapolateRight: "clamp" });
    return (
      <AbsoluteFill style={{ justifyContent: "space-between", padding: "160px 48px", opacity }}>
        <div style={{ alignSelf: "flex-end", fontSize: 56, fontFamily: "Georgia, serif", letterSpacing: "0.2em", color: "#1A1A1A", textTransform: "uppercase" as const }}>
          BEAUTY
        </div>
        <div style={{ alignSelf: "flex-start", fontSize: 32, fontFamily: "Hiragino Sans, sans-serif", color: "#555555" }}>
          美しさの新基準
        </div>
      </AbsoluteFill>
    );
  },
},
```

**P8（下部帯テキスト）— 帯divを挟む + 文字が下から上に出現（デフォルトアニメーションB）:**
```tsx
{
  file: "CLIP_FILE.mp4",
  durationInFrames: 150,
  render: (frame: number) => (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "stretch",
      opacity: interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateY(${interpolate(frame, [0, 20], [40, 0], { extrapolateRight: "clamp" })}px)`,
    }}>
      <div style={{ backgroundColor: "rgba(0,0,0,0.45)", paddingTop: 20, paddingBottom: 28, paddingLeft: 48, paddingRight: 48, textAlign: "center" as const }}>
        <div style={{ fontSize: 52, fontWeight: 500, color: "#FFFFFF", letterSpacing: "0.18em", display: "flex", justifyContent: "center", overflow: "hidden" }}>
          {"テロップテキスト".split("").map((char, i) => {
            const age = Math.max(0, frame - i * 5);
            const t = Math.min(1, age / 20);
            return (
              <span key={i} style={{ opacity: t, transform: `translateY(${(1 - t) * 30}px)`, display: "inline-block" }}>{char}</span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  ),
},
```

#### 実装時の注意点

- **Remotionの制約**: `AbsoluteFill` は `display: flex, flexDirection: column` がデフォルト
  - 下部配置 → `justifyContent: "flex-end"`
  - 右端 → `alignItems: "flex-end"`
  - 中央 → `justifyContent: "center", alignItems: "center"`
- **縦書き**: `writingMode: "vertical-rl"`
- **patterns.mdのCSS実装例を使う**（コピペして値を調整）

---

### Step 6: デザインチェックリスト（実装後）

- [ ] 3秒で内容が理解できるか
- [ ] 主役が1つになっているか
- [ ] 3シーンでフォントweight・配置・サイズに変化があるか
- [ ] 前回の動画と異なるデザインになっているか

チェック完了後、Step 7へ進む。

---

### Step 7: デザイン批評（バナーとの比較）

実装が終わったらRemotion CLIで静止フレームを書き出し、参考バナーと並べて比較する。

#### 7-1. 各シーンのフレームを書き出す

各クリップの開始フレームを AdVideo.tsx の clips 配列から計算して使う。
各クリップの中間フレーム（開始 + durationInFrames/2）を書き出すと映像とテロップが両方見える。

```bash
# python3でclips配列からフレーム番号を計算する例
python3 -c "
clips = [150, 150, 150]  # 実際のdurationInFramesに書き換える
start = 0
for i, d in enumerate(clips):
    mid = start + d // 2
    print(f'scene{i+1}: --frame={mid}')
    start += d
"
```

計算結果のフレーム番号を使って書き出す:
```bash
cd /Users/keeee/Desktop/Dev/OssMovieAIz
npx remotion still src/index.ts AdVideo /tmp/telop-still-scene1.png --frame=[scene1のmidフレーム]
npx remotion still src/index.ts AdVideo /tmp/telop-still-scene2.png --frame=[scene2のmidフレーム]
npx remotion still src/index.ts AdVideo /tmp/telop-still-scene3.png --frame=[scene3のmidフレーム]
```

#### 7-2. フレームと参考バナーを読み込んで比較する

各シーンのフレーム（/tmp/telop-still-sceneX.png）と Step 4 で選んだパターンの代表バナーを Read で読み込む。
代表バナーは `/Users/keeee/Desktop/Dev/OssMovieAIz/skills/telop-design/banners/` に保存されている。
例: P1なら `P1_下部左寄せ太ゴシック_TOANN.jpg`

以下を確認する：

| 確認項目 | 判定基準 |
|---------|---------|
| **配置の一致** | バナーと同じエリアにテキストが置かれているか |
| **フォントwightの一致** | 太さが再現できているか（太ゴシックなら太ゴシックか） |
| **サイズ感の一致** | 映像に対するテキストのサイズ比率が近いか |
| **色の一致** | 白/暗色/アクセントが意図通りか |
| **余白の一致** | テキスト周りの空気感が再現できているか |
| **可読性** | 5秒で読めるか。文字が映像に埋もれていないか |

#### 7-3. ズレがあれば修正してから完了とする

比較の結果ズレがあった場合は、AdVideo.tsxのスタイル値を調整して再度 7-1 を実行する。
「なんとなく似ている」ではなく「同じデザイン処理が再現できている」状態になってから完了とする。

修正が完了したらユーザーに報告する：
```
✅ テロップデザイン実装完了
- Scene 1: [パターン名] — [1行コメント]
- Scene 2: [パターン名] — [1行コメント]
- Scene 3: [パターン名] — [1行コメント]
Remotion Studio (http://localhost:3000) で動きを確認してください。
```

---

### Step 8: アニメーションのカスタマイズ（オプション）

デフォルト実装後にユーザーがアニメーションを変更したい場合のフロー。

#### 参考サイト
- CodePen: https://codepen.io/search/pens?q=text+js+animation
- anime.js: https://animejs.com/documentation/text

#### 手順
1. ユーザーが気に入ったエフェクトのURLまたはJSコードを提示する
2. コードを解析して動きを把握する
3. `useCurrentFrame()` で決定論的に再現する（setInterval・requestAnimationFrame・Math.random は使えない）
4. 対象シーンのrender関数を差し替える

#### useCurrentFrame()変換の原則
| 元コード | 変換方法 |
|---------|---------|
| `setInterval(fn, ms)` | `Math.floor(frame / (ms/1000*30))` でtick数を計算 |
| `requestAnimationFrame` | frameが毎フレーム1ずつ増えるので不要 |
| `Math.random()` | `Math.sin(i * seed) * 43758.5453` の小数部で代替 |
| `animation-delay: i * Nms` | `frame - i * Math.round(N/1000*30)` で各文字のローカルフレームを計算 |
| CSS `@keyframes` | `interpolate` または `Math.sin/pow` で同等のイージングを実装 |

#### 注意
- canvasのgetImageData・ピクセル操作を使うエフェクトは再現困難。その場合は「似た雰囲気の別アプローチ」を提案する
- 再帰的な状態（前フレームの値が次フレームに影響）を持つエフェクトも再現が難しい場合がある

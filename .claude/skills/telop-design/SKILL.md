---
name: telop-design
description: 映像クリップ完成後に、bsテロップスタイルをベースにしつつ実際の映像に合わない部分だけ調整し、テロップ文言もbsの文字数・役割を維持して書き換える。テロップの最適化・文言作成・AdVideo.tsx実装までを一貫して行う。
allowed-tools: Bash(ffmpeg *), Bash(ffprobe *), Bash(ls *), Bash(curl *), Bash(mkdir *), Bash(python3 *), Bash(npx *), Read, Write, WebFetch
---

## テロップ最適化・文言作成・実装

映像クリップが完成した後に発動するスキル。bsで丸コピーしたテロップスタイルをベースに、実際の映像との相性をチェックし、問題があるシーンだけスタイルを調整する。同時にテロップ文言もbsの文字数・役割を維持して新テーマに書き換える。

---

### 絶対ルール（最重要）

1. **bsテロップスタイルが「デフォルト正解」**。全部捨てて作り直さない。映像に合わない部分だけ直す。
2. **テロップ文言はbsの文字数帯・役割を維持する**。短いキャッチコピーを長い説明文に膨らませない。
3. **各シーンに異なるパターンを使う**。3シーンで同じパターン・同じフォントweightを使わない。
4. **フォントサイズは64px未満にしない**。動画は5秒で消える。小さいと読めない。
5. **アニメーションは全シーン共通で `animC`（タイプライター式blurフェードイン）を使う**。
6. **AdVideo.tsx実装時はWriteツールを使わず、Bashのヒアドキュメント（`cat <<'EOF'`）で上書きする**。前回のコードを読まないための強制リセット。

---

### デフォルトアニメーション標準（全シーン共通）

**全シーン必ずこのアニメーションを使う。** 文字がタイプライター式に順番に現れ、blurが溶けながら40フレームかけてフェードイン。実装はファイル冒頭に共通関数 `animC` を定義して全シーンで呼び出す。

> **注意:** CHARS_DURATIONとFADE_FRAMESはクリップの尺に合わせて調整する。短いクリップ（30〜105f）にはCHARS_DURATION=8, FADE_FRAMES=12程度にしないと文字が見えない。

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

### Step 1: 現状の把握

以下を読み込む：

```
Read: .claude/skills/telop-design/patterns.md
Read: .claude/skills/telop-design/matching-rules.md
Read: .claude/skills/telop-design/fonts-colors-decorations.md
Read: デザインの極意書.md
Read: src/compositions/AdVideo.tsx（※bsで実装済みのスタイルを確認するため）
```

AdVideo.tsxから**bsテロップの情報を抽出**する：
- 各シーンのテロップ文言（原文）
- 各シーンの文字数
- 各シーンの役割（フック/本題/CTA）
- 各シーンのスタイル（配置・フォント・サイズ・色・装飾）

これらを「bsベースライン」として記録する。

---

### Step 2: 映像フレームの分析

#### 2-1. クリップの確認

```bash
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/*.mp4
```

使用するクリップとdurationInFrames（fps30換算）を確認する。

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

### Step 3: bsスタイルと映像の相性チェック

**各シーンについて、bsベースラインのスタイルと実映像を照合する。**

| チェック項目 | 判定基準 | 問題があれば |
|------------|---------|------------|
| **被写体との重なり** | テロップが被写体の顔や重要部分と被っていないか | 配置を変更（上↔下、左↔右） |
| **コントラスト** | テキスト色と背景の明暗差は十分か | 色・縁取り・シャドウを調整 |
| **空きスペース** | bsの配置位置に実映像で空きがあるか | 空いている場所へ移動 |
| **雰囲気の一致** | bsのフォント・装飾が実映像の雰囲気に合うか | パターン辞書から代替を選択 |

**判定結果は3段階:**
- **OK** — bsスタイルそのままで問題なし → 変更なし
- **微調整** — 配置やサイズの数値を少し変える程度 → 値だけ修正
- **パターン変更** — 根本的に合わない → matching-rules.mdの判定フローで新パターンを選択

---

### Step 4: テロップ文言の作成

**bsテロップの「文字数」と「役割」を維持して、新テーマに合わせた文言を作る。**

#### 文字数維持ルール

| bsテロップの文字数 | 役割 | 新テキストの制約 |
|-----------------|------|---------------|
| 1-4文字 | キャッチコピー（一言で刺す） | 同じ1-4文字で作る。説明しない |
| 5-8文字 | 短文コピー（要点1つ） | 同じ5-8文字で作る。2つの情報を詰め込まない |
| 9-12文字 | 中文コピー | 同じ9-12文字で作る |
| 13文字以上 | 説明文 | 同等の文字数で作る |

#### シーン尺との整合

| シーンの尺 | テロップの最大文字数目安 |
|----------|-------------------|
| 3秒以下（90f以下） | 5文字 |
| 4-5秒（120-150f） | 10文字 |
| 6秒以上（180f以上） | 制限なし |

#### 行数維持ルール

- bsテロップが1行 → 新テキストも必ず1行。文字数が増えてもフォントサイズ縮小で1行に収める（`calcFontSize()`使用）
- bsテロップが2行 → 新テキストも2行以内

#### 文言作成の手順

1. bsテロップの各シーンの文字数・役割・行数を確認
2. ユーザーのテーマに合わせて、**同じ器のサイズ**で中身を書き換える
3. キャッチコピーはキャッチコピーとして作る。説明文にしない
4. 提案時にbs原文と並べて見せる：
   ```
   Scene 1（フック・3文字）: bs「衝撃！」→ 新「驚愕！」
   Scene 2（本題・8文字）: bs「これが噂の新技術」→ 新「まつ毛が生まれ変わる」
   Scene 3（CTA・5文字）: bs「今すぐ予約」→ 新「無料で体験」
   ```

---

### Step 5: テロップデザイン提案

各シーンについて以下を提案する。

```
【scene1_XXX — フック】
bsスタイル: P1 下部左寄せ太ゴシック / 84px / #FFFFFF
映像チェック: OK（被写体は上部、下部に空きあり）
→ bsスタイルのまま使用
テロップ文言: bs「衝撃！」(3文字) → 新「驚愕！」(3文字)

【scene2_XXX — 本題】
bsスタイル: P3 上部大文字ヘッドライン / 96px / #FFFFFF
映像チェック: 要調整（被写体が上部にいるため重なる）
→ P1 下部左寄せに変更。フォント・色はbsを維持
テロップ文言: bs「これが噂の新技術」(8文字) → 新「まつ毛が生まれ変わる」(9文字)

【scene3_XXX — CTA】
bsスタイル: P8 下部帯テキスト / 52px / #FFFFFF
映像チェック: OK
→ bsスタイルのまま使用
テロップ文言: bs「今すぐ予約」(5文字) → 新「無料で体験」(5文字)
```

ユーザーに確認：「この方向性でよければ実装します。」

---

### Step 6: AdVideo.tsxを実装する

**Bashのヒアドキュメントで上書きする。** 前回のコードは参照しない。

Step 1で取得したbsベースラインのスタイル値をベースに、Step 5で決めた調整を反映する。

#### デフォルトスタイル（bsスタイルが不明な場合のフォールバック）

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
        /* bsスタイル（またはStep 5で調整した値） */
      }}>
        <div style={{
          /* bsスタイル（またはStep 5で調整した値） */
        }}>
          {animC(frame, "新テロップ文言")}
        </div>
      </AbsoluteFill>
    ),
  },
  // ... 他のクリップも同様
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

**P8（下部帯テキスト）— 帯divを挟む + 文字が下から上に出現:**
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

### Step 7: デザインチェックリスト（実装後）

- [ ] 3秒で内容が理解できるか
- [ ] 主役が1つになっているか
- [ ] 3シーンでフォントweight・配置・サイズに変化があるか
- [ ] テロップ文言がbsの文字数帯を維持しているか
- [ ] キャッチコピーが説明文に膨らんでいないか
- [ ] bsスタイルからの変更は映像との相性問題がある箇所だけか

チェック完了後、Step 8へ進む。

---

### Step 8: デザイン批評（バナーとの比較）

実装が終わったらRemotion CLIで静止フレームを書き出し、映像との相性を最終確認する。

#### 8-1. 各シーンのフレームを書き出す

各クリップの中間フレーム（開始 + durationInFrames/2）を書き出す。

```bash
python3 -c "
clips = [150, 150, 150]  # 実際のdurationInFramesに書き換える
start = 0
for i, d in enumerate(clips):
    mid = start + d // 2
    print(f'scene{i+1}: --frame={mid}')
    start += d
"
```

```bash
cd /Users/keeee/Desktop/Dev/OssMovieAIz
npx remotion still src/index.ts AdVideo /tmp/telop-still-scene1.png --frame=[scene1のmidフレーム]
npx remotion still src/index.ts AdVideo /tmp/telop-still-scene2.png --frame=[scene2のmidフレーム]
npx remotion still src/index.ts AdVideo /tmp/telop-still-scene3.png --frame=[scene3のmidフレーム]
```

#### 8-2. フレームを読み込んで確認する

各シーンのフレーム（/tmp/telop-still-sceneX.png）をReadで読み込み、以下を確認：

| 確認項目 | 判定基準 |
|---------|---------|
| **被写体との重なり** | テロップが被写体の重要部分と被っていないか |
| **コントラスト** | 背景に対してテキストが十分に読めるか |
| **サイズ感** | 映像に対するテキストのサイズ比率が適切か |
| **可読性** | 5秒で読めるか。文字が映像に埋もれていないか |

#### 8-3. ズレがあれば修正してから完了とする

修正が完了したらユーザーに報告する：
```
✅ テロップ最適化完了
- Scene 1: [bsスタイル維持 or 変更内容] — 「新テロップ文言」(N文字)
- Scene 2: [bsスタイル維持 or 変更内容] — 「新テロップ文言」(N文字)
- Scene 3: [bsスタイル維持 or 変更内容] — 「新テロップ文言」(N文字)
bs変更箇所: N/3シーン
Remotion Studio (http://localhost:3000) で動きを確認してください。
```

---

### Step 9: アニメーションのカスタマイズ（オプション）

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

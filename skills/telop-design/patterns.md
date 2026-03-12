# テロップデザインパターン辞書

bannnner.comのバナー45枚から帰納的に抽出した、動画テロップに転用可能なテキスト処理パターン。

---

## P1: 下部左寄せ太ゴシック型

**元バナー:** TOANN (8339), On Running (8434, 8418, 8382, 8327)

### 特徴
- 配置: 下部、左寄せ（paddingLeft: 48-64）
- フォント: 太ゴシック（weight 700-800）
- サイズ: **大きめ 72-96px**（画面幅の7-9%）
- 色: 白（暗背景）またはダークカラー（明背景）
- 装飾: テキストシャドウのみ（影は控えめ）
- 改行: 2行まで。1行目がメイン、2行目が補足
- 余白: 下端から100-160px、テキスト周りに十分な空気感

### 使いどころ
- 暗背景 or 被写体が上部に集中する映像
- 商品クローズアップ、シネマティック
- 力強いメッセージ、フック系テロップ

### CSS実装
```js
{
  // 配置: 下部左寄せ
  justifyContent: "flex-end",
  alignItems: "flex-start",
  paddingBottom: 140,
  paddingLeft: 56,
  // テキスト
  fontSize: 84,
  fontWeight: 800,
  fontFamily: "Hiragino Sans, sans-serif",
  letterSpacing: "0.02em",
  lineHeight: 1.3,
  color: "#FFFFFF",
  textShadow: "0 2px 16px rgba(0,0,0,0.4)",
  whiteSpace: "pre-line",
}
```

---

## P2: 中央ブランドロゴ型

**元バナー:** BOTTEGA VENETA (8387), 4°C BRIDAL (8163, 8152), Miss Dior (8240), BRILLAMICO (8133)

### 特徴
- 配置: 中央〜やや下
- フォント: セリフ体（明朝）、weight 300-400
- サイズ: バナー56-72px → **動画88-96px**
- 色: 白（暗背景）またはダークグレー（明背景）
- 装飾: **完全に素テキスト。影も帯もなし**
- letter-spacing: 広め（0.15-0.3em）
- 余白: 周囲に大量の余白。テキストが「浮いている」印象

### 使いどころ
- 高級感・ブランディング
- 余白が多い映像、商品が小さく映る構図
- ブランド名やキャッチコピーが短い（8文字以下）

### CSS実装
```js
{
  // 配置: 中央
  justifyContent: "center",
  alignItems: "center",
  // テキスト（動画向けスケール済み）
  fontSize: 92,       // バナー64px × 1.5倍
  fontWeight: 300,
  fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
  letterSpacing: "0.25em",
  lineHeight: 1.5,
  color: "#FFFFFF", // or "#1A1A1A"
}
```

---

## P3: 上部大文字ヘッドライン型

**元バナー:** willone (8255), 肌ラボ (8444), Meltykiss (8368)

### 特徴
- 配置: 上部、左寄せまたは中央
- フォント: **超太ゴシック（weight 800-900）**
- サイズ: **最大級 80-120px**（画面の8-11%）
- 色: 白 or 濃色（背景とのコントラスト最大化）
- 改行: 2-3行に分割して「階段状」に配置
- 装飾: テキストシャドウ。場合により小さいサブテキストを添える
- letter-spacing: タイト〜標準（0-0.04em）

### 使いどころ
- **フック・インパクト重視のシーン**
- 人物が下部にいる映像（上部に空きがある）
- 短いパンチのある言葉

### CSS実装
```js
{
  // 配置: 上部左寄せ
  justifyContent: "flex-start",
  alignItems: "flex-start",
  paddingTop: 160,
  paddingLeft: 48,
  // テキスト
  fontSize: 96,
  fontWeight: 900,
  fontFamily: "Hiragino Sans, sans-serif",
  letterSpacing: "0.02em",
  lineHeight: 1.25,
  color: "#FFFFFF",
  textShadow: "0 3px 24px rgba(0,0,0,0.5)",
  whiteSpace: "pre-line",
}
```

---

## P4: 縦書き端配置型

**元バナー:** 金麦晩酌 (8449), 牛肉あったか鍋 (8376)

### 特徴
- 配置: 右端 or 左端（paddingRight/Left: 48-80）
- フォント: 明朝体 or ゴシック（内容で使い分け）
- サイズ: 大きめ 64-80px
- 色: 白（暗背景）、淡色系（ゴールド、ベージュ）
- writingMode: vertical-rl
- 装飾: 控えめなテキストシャドウ or なし
- letter-spacing: 広め（0.2-0.4em）

### 使いどころ
- **和風・高級感・情緒的な表現**
- 被写体が中央にある映像（左右端が空く）
- 詩的・エモーショナルなコピー

### CSS実装
```js
{
  // 配置: 右端中央
  justifyContent: "center",
  alignItems: "flex-end",
  paddingRight: 64,
  // テキスト
  writingMode: "vertical-rl",
  fontSize: 72,
  fontWeight: 300,
  fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
  letterSpacing: "0.3em",
  lineHeight: 1,
  color: "#F5E6C8", // or "#FFFFFF"
  textShadow: "0 1px 16px rgba(0,0,0,0.4)",
}
```

---

## P5: 左上ミニマル型

**元バナー:** IPSA (8172), LUQUE (8372), JINS (8336)

### 特徴
- 配置: 左上
- フォント: **細ゴシック or 細明朝（weight 200-400）**
- サイズ: 小〜中 40-56px
- 色: ダークグレー (#2A2A2A〜#555) or 白
- 装飾: **完全になし**。最もミニマル
- letter-spacing: やや広め（0.08-0.15em）
- 複数行でも等間隔に静かに並ぶ

### 使いどころ
- 明るい背景、白背景
- 清潔感・上品さが求められるスキンケア・美容
- 行動喚起（CTA）など控えめなテキスト

### CSS実装
```js
{
  // 配置: 左上
  justifyContent: "flex-start",
  alignItems: "flex-start",
  paddingTop: 180,
  paddingLeft: 56,
  // テキスト
  fontSize: 48,
  fontWeight: 300,
  fontFamily: "Hiragino Sans, sans-serif",
  letterSpacing: "0.1em",
  lineHeight: 1.6,
  color: "#2A2A2A",
}
```

---

## P6: 中央インパクト数字型

**元バナー:** AOKI (8370), Oisix (8392), MAKE KEEP MIST (8242)

### 特徴
- 配置: 中央
- フォント: **極太ゴシック（weight 900）**
- サイズ: **超大 100-160px**（数字・キーワード部分のみ）
- 色: 赤 (#E53935)、アクセントカラー、または白
- 装飾: 縁取り、背景帯、グラデーション。装飾が多い
- 数字・キーワードだけ巨大にして周囲に小さい補足を配置

### 使いどころ
- セール・キャンペーン・数字訴求
- エネルギッシュでカジュアルな映像
- **高級感には不向き**

### CSS実装
```js
// コンテナ
{
  // 配置: 中央
  justifyContent: "center",
  alignItems: "center",
}
// メインテキスト（数字）
{
  fontSize: 140,
  fontWeight: 900,
  fontFamily: "Hiragino Sans, sans-serif",
  color: "#E53935",
  WebkitTextStroke: "2px #FFFFFF", // 縁取り
}
// サブテキスト
{
  fontSize: 36,
  fontWeight: 400,
  fontFamily: "Hiragino Sans, sans-serif",
  color: "#FFFFFF",
}
```

---

## P7: 英字セリフ＋日本語組み合わせ型

**元バナー:** MASTER PIECES (7869), GOOD ITEMS HUNTER (8267), DIOR CAPTURE (8423)

### 特徴
- 配置: 英字が右上 or 上部、日本語が左下 or 下部
- フォント: 英字はセリフ体（大・weight 300-400）、日本語はゴシック（小・weight 400）
- サイズ: 英字 バナー48-72px → **動画72-96px** / 日本語 バナー28-40px → **動画56-72px**
- 色: 同系色でトーンを変える（白+薄グレー、黒+グレー）
- letter-spacing: 英字は広め（0.15-0.3em）
- 2つのテキスト要素で視線の対角線を作る

### 使いどころ
- おしゃれ・モード系映像
- ブランド名が英語の広告
- 情報を2階層で見せたい

### CSS実装
```js
// 英字（上部・動画向けスケール済み）
{
  fontSize: 80,       // バナー56px × 1.5倍
  fontWeight: 300,
  fontFamily: "Georgia, 'Times New Roman', serif",
  letterSpacing: "0.2em",
  color: "#1A1A1A",
  textTransform: "uppercase",
}
// 日本語（下部・動画向けスケール済み）
{
  fontSize: 64,       // バナー32px × 2倍
  fontWeight: 400,
  fontFamily: "Hiragino Sans, sans-serif",
  letterSpacing: "0.05em",
  color: "#555555",
}
```

---

## P8: 下部帯テキスト型

**元バナー:** G-SHOCK (8146), CASIO OCEANUS (7725), アン・ソン・ベニール (8337)

### 特徴
- 配置: 下部全幅 or 下部中央
- フォント: ゴシック or 明朝（weight 400-600）
- サイズ: 中 44-60px
- 色: 白テキスト
- 装飾: **半透明の背景帯**（黒 30-50%透過）
- 帯のpadding: 上下16-24px
- テロップの王道。視認性が最も高い

### 使いどころ
- **どんな映像にも使える万能型**
- 背景が複雑で文字が読みにくい場合
- 情報伝達を最優先するCTA・説明テキスト

### CSS実装
```js
// 帯コンテナ
{
  // 配置: 下部全幅
  justifyContent: "flex-end",
  alignItems: "stretch",
}
// 帯本体
{
  backgroundColor: "rgba(0,0,0,0.45)",
  paddingTop: 20,
  paddingBottom: 20,
  paddingLeft: 48,
  paddingRight: 48,
  textAlign: "center",
}
// テキスト
{
  fontSize: 52,
  fontWeight: 500,
  fontFamily: "Hiragino Sans, sans-serif",
  letterSpacing: "0.06em",
  color: "#FFFFFF",
}
```

---

## P9: 背景色ベタ＋大文字型

**元バナー:** コカ・コーラ (8453), キューピー (8429), XEBIO (8446)

### 特徴
- 配置: 全面 or 上半分/下半分
- フォント: **極太ゴシック（weight 800-900）**
- サイズ: 大 72-100px
- 色: 白テキスト on カラー背景（赤、黄、青など）
- 装飾: 背景色がベタ塗り。テキストが直接乗る
- 情報量多め、複数要素を配置

### 使いどころ
- カジュアル・ポップ・食品系
- セール・キャンペーン
- **高級感には不向き。親しみやすさ重視**

### CSS実装
```js
// 背景ブロック
{
  backgroundColor: "#D32F2F", // or ブランドカラー
  padding: "24px 40px",
}
// テキスト
{
  fontSize: 80,
  fontWeight: 900,
  fontFamily: "Hiragino Sans, sans-serif",
  color: "#FFFFFF",
  letterSpacing: "0.02em",
  lineHeight: 1.2,
}
```

---

## P10: 筆書き・手書き風型

**元バナー:** 板前魂 (8379), 福さ屋 (8329)

### 特徴
- 配置: 中央 or やや上
- フォント: 筆書き風（※Remotionでは擬似的に明朝太字で代用）
- サイズ: 大 80-120px
- 色: 黒 or 赤（和風）
- 装飾: なし or 朱印風の囲み
- 和の伝統的なインパクト

### 使いどころ
- 和食・日本酒・伝統的なもの
- お正月・季節イベント

### CSS実装（明朝太字で代用）
```js
{
  fontSize: 96,
  fontWeight: 900,
  fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
  color: "#1A1A1A", // or "#B71C1C"
  letterSpacing: "-0.02em", // 詰め気味
  lineHeight: 1.1,
}
```

---

## フォントサイズ目安（1080×1920 縦型動画）

動画テロップは**バナーより大きく**する。バナーは静止画で読む時間があるが、動画は5秒で消える。

**スケール係数: バナーの数値 × 1.5〜2倍を動画推奨値とする。**

| 用途 | バナー参考値 | 動画推奨値 | 動画最小 |
|------|------------|----------|---------|
| メインテロップ | 40-64px | **80-96px** | 72px |
| サブテキスト | 28-40px | **56-72px** | 48px |
| CTA・補足 | 24-32px | **48-56px** | 40px |

**絶対ルール: メインテロップは72px未満にしない。サブテキストは48px未満にしない。**

---

## パターン早見表

| パターン | 雰囲気 | フォント | サイズ | 配置 |
|---------|--------|---------|--------|------|
| P1 下部左寄せ太ゴシック | 力強い・スポーティ | 太ゴシック | 大 84px | 下部左 |
| P2 中央ブランドロゴ | 高級・ブランド | 細明朝 | 中 64px | 中央 |
| P3 上部大文字ヘッドライン | インパクト・フック | 超太ゴシック | 最大 96px | 上部左 |
| P4 縦書き端配置 | 和風・情緒的 | 明朝 | 大 72px | 右端/左端 |
| P5 左上ミニマル | 清潔・上品 | 細ゴシック | 小 48px | 左上 |
| P6 中央インパクト数字 | セール・カジュアル | 極太ゴシック | 超大 140px | 中央 |
| P7 英字+日本語二層 | モード・おしゃれ | セリフ+ゴシック | 英56/日32px | 対角線 |
| P8 下部帯テキスト | 万能・視認性重視 | ゴシック | 中 52px | 下部全幅 |
| P9 背景色ベタ+大文字 | ポップ・カジュアル | 極太ゴシック | 大 80px | 全面 |
| P10 筆書き風 | 和風・伝統 | 明朝太字 | 大 96px | 中央 |

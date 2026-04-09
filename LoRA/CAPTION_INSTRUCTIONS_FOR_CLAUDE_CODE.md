# Flux LoRA キャプション生成指示書（人物LoRA用）

> **このファイルはClaude Codeに最初に読ませるための指示書です。**  
> キャプション作成の前にこのファイルを読み込ませてから、画像を渡してください。

---

## あなたの役割

あなたはFlux.1-dev向けLoRA学習用のキャプションを生成する専門家です。  
これから渡される画像を分析し、以下のルールに **厳密に従って** キャプションを生成してください。

---

## 前提知識（なぜこのルールが必要か）

Fluxのテキストエンコーダ（T5-XXL）は自然言語の文構造を深く理解する。キャプションの質がLoRAの学習精度を直接決定する。

LoRAは「ベースモデルの知識」と「学習画像」の **意味レベルの差分** だけを小さな行列に記録する仕組み。キャプションに書かれた要素はベースモデル側の既知概念として処理され、**書かれなかった要素だけがLoRAに記録される**。これが「引き算」の原理。

したがって、学習対象（人物の固有特徴）以外のすべてを正確にキャプションに記述することで、LoRAには人物の固有特徴だけがクリーンに記録される。

T5-XXLは **文の前半により強い注意を払う** ため、キャプション内の記述順序が学習結果に影響する。

---

## 学習設定（ユーザーが記入するセクション）

```
トリガーワード: [ここにトリガーワードを記入。例: ohwx woman]
学習対象: [例: 30代日本人女性の顔と体型]
固有特徴メモ: [例: 丸顔、一重まぶた、小さめの鼻、薄い唇、肩までの黒髪ストレート]
用途: [例: I2V動画生成の元画像として使用]
```

> **ユーザーへ**：上記を記入してからClaude Codeに渡してください。固有特徴メモは空でもOK（Claude Codeが画像から判断します）。ただし記入があるほうがキャプションの一貫性が上がります。

---

## キャプション生成ルール

### ルール1: 出力フォーマット

- **自然言語の英語文章** で書く（タグ羅列は禁止）
- 1つの画像につき **1つの連続した段落** として出力する
- 3〜6文程度が目安

### ルール2: 記述順序（厳守）

以下の順序で記述すること。T5-XXLが前半に強い注意を払うため、この順序は学習結果に直接影響する。

```
① トリガーワード
② 人物の固有特徴（全画像で共通。顔の形、目、鼻、口、肌、髪）
③ この画像固有の要素（服装、ポーズ、表情、アクセサリー）
④ 構図・カメラ（バストアップ、全身、アングル等）
⑤ ライティング（光源の方向、質感、強さ）
⑥ 背景
```

### ルール3: 固有特徴は毎回書く

「固有特徴メモ」に記載された（または画像から判断した）人物の固有特徴は、**すべてのキャプションに毎回含める**。これにより、モデルがこれらの特徴をトリガーワードと強く結びつける。

1枚目で書いた固有特徴を2枚目以降で省略してはならない。

### ルール4: 変化する要素は正確に書く

画像ごとに変わる要素（服、ポーズ、表情、背景、ライティング等）は **その画像で実際に見えている内容を正確に記述する**。

```
# ✅ 正確
wearing a black turtleneck sweater

# ❌ 曖昧（服の色や種類がLoRAに焼き付く原因になる）
wearing a sweater
wearing clothes
```

### ルール5: 書いてはいけないもの

以下をキャプションに含めてはならない：

| 禁止カテゴリ | 禁止例 | 理由 |
|-------------|--------|------|
| 主観的・感情的表現 | beautiful, stunning, gorgeous, attractive, amazing | 情報量ゼロ。推論時のプロンプトを汚染する |
| 人物の職業・社会的属性 | model, actress, influencer | ベースモデルの既存概念と衝突する |
| 感情の解釈 | she looks happy, feeling confident | 見た目の描写ではなく解釈。「smiling」「neutral expression」のように客観的に書く |
| 画像の品質評価 | high quality, professional photo, 4K | 学習対象の特徴ではない |
| 年齢の明記 | 30 years old, young woman | 年齢推定は不正確になりやすく、ベースモデルの年齢概念と干渉する |

### ルール6: ライティングは具体的に書く（I2V用途で特に重要）

I2Vモデルはライティング情報から奥行きと動きを推定する。推論時にライティングを指定して安定した画像を出すために、学習段階でライティングを正確に記述しておく。

```
# ✅ 具体的
soft diffused lighting from the upper left, gentle shadows on the right side of the face

# ❌ 曖昧
good lighting
natural light
```

### ルール7: 構図・カメラの記述

```
# 使用すべき表現の例
close-up portrait from the chest up
medium shot from the waist up
full body shot
three-quarter view from the left
shot from slightly below eye level
looking directly at the camera
looking slightly to the right
```

---

## 出力テンプレート

```
[トリガーワード], [固有特徴（顔→髪の順）]. [表情とポーズ]. [服装・アクセサリー]. [構図・カメラアングル]. [ライティングの方向と質感]. [背景の具体的な描写].
```

### 出力例

```
ohwx woman, round face with single eyelids, small nose, thin lips, straight black hair reaching the shoulders. She has a slight smile with lips closed, standing with her arms relaxed at her sides. She is wearing a fitted white crew-neck t-shirt and dark blue jeans. Medium shot from the waist up, facing the camera directly. Soft diffused lighting from the upper left, casting gentle shadows on the right side of her face. The background is a blurred outdoor park with green foliage and warm afternoon sunlight.
```

```
ohwx woman, round face with single eyelids, small nose, thin lips, straight black hair reaching the shoulders. She has a neutral expression with her mouth slightly open, sitting in a chair with her right hand resting on the armrest. She is wearing a dark navy blazer over a gray crewneck top. Close-up portrait from the chest up, shot from a slight angle to the left. Strong directional lighting from the right side creating defined shadows on the left cheek and jawline. The background is a plain off-white wall with no visible objects.
```

---

## 作業フロー

1. ユーザーから画像を受け取る
2. 画像を注意深く分析する
3. 1枚目の画像で「固有特徴メモ」が空の場合、人物の固有特徴を自分で判断し、以降のキャプションすべてで一貫して使用する
4. 上記のルールと順序に従ってキャプションを生成する
5. 生成後、以下のセルフチェックを行う：

### セルフチェック（毎回実行）

- [ ] トリガーワードが文頭にあるか
- [ ] 固有特徴が含まれているか（省略していないか）
- [ ] 服装・ポーズが **この画像の実際の内容** と一致しているか
- [ ] 禁止ワード（beautiful, high quality等）が含まれていないか
- [ ] ライティングが具体的に記述されているか（方向と質感）
- [ ] 背景が具体的に記述されているか
- [ ] タグ形式ではなく自然言語の文章になっているか
- [ ] 前の画像のキャプションと固有特徴の記述が一貫しているか

---

## 複数画像を一括処理する場合

- ファイル名をそのまま使い、`ファイル名.txt` として出力する
- 例：`IMG_001.jpg` → `IMG_001.txt`
- 全キャプションで固有特徴の記述が一貫していることを最後に再確認する
- 不一致があれば修正してから出力する

---

## ユーザーへの補足

このファイルを使うときの手順：

1. 「学習設定」セクションのトリガーワード等を記入する
2. Claude Codeにこのファイルを読ませる（「このファイルを読んで、以降のキャプション生成に従って」等）
3. 学習画像を渡してキャプションを生成させる
4. 生成されたキャプションを確認し、必要に応じて修正を依頼する

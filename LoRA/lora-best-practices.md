# LoRA作成 ベストプラクティス（Flux.1-dev）

> このドキュメントはClaude Codeに読ませて、LoRA学習の設計・トラブルシュート時に参照するためのリファレンスです。
> 推奨ツール：ai-toolkit（Ostris）  
> 補助ツール：kohya_ss（sd-scripts）※Flux対応済みだが情報量・安定性でai-toolkitが優位  
> 対応モデル：Flux.1-dev

---

## 核心原則

LoRA学習の本質は **「AIに何を覚えさせ、何を忘れさせるか」を緻密にコントロールすること** である。数より質、そして「引き算」の設計思想が成功の鍵。

---

## 0. LoRAの仕組みを理解する（概念セクション）

LoRA学習を正しく設計するには、裏で何が起きているかを把握することが重要。

### 0-1. 潜在空間（Latent Space）とVAE

ベースモデルは画像をピクセル単位で直接扱わない。画像はまず **VAE（Variational Auto-Encoder：変分オートエンコーダ）** によって「潜在空間」に圧縮される。

- **潜在空間とは**：画像のピクセル（表面的な数値）を「意味的な本質」に変換した空間。512×512の画像（約235万個の数値）が、64×64×16程度の小さなテンソルに圧縮される
- **なぜピクセル単位ではダメか**：
  - 計算量が膨大すぎる
  - 隣接ピクセルの冗長性が高く、無駄な情報が多い
  - 同じ人物でもライティングが変わるだけでピクセル値が全く違うため、「同一人物である」という共通性を見つけるのが困難
- **潜在空間の利点**：似た意味を持つ画像は近い場所に配置される。微笑んでいる顔と少し口角が上がった顔は近く、全く別の被写体は遠い。この「意味の距離」のおかげで効率的に学習できる

**実用上の重要ポイント**：JPEGの圧縮ノイズやアーティファクトがある画像をVAEに通すと、そのノイズも「意味のある特徴」として圧縮されてしまう。だから学習画像は **できるだけ高品質なPNG・無圧縮に近い状態** で用意すべき。

### 0-2. LoRAとは何か — 「差分を小さな行列に記録する」

ニューラルネットワークの正体は、数値を縦横に並べた「行列」が何百層も積み重なったもの。画像生成では、行列の掛け算の連鎖で「テキスト条件とノイズから画像を生成する」変換を実現している。

- **フルファインチューニング**：ベースモデルの巨大な行列（例：4096×4096 = 約1600万個の数値）を直接書き換える。コストが高く、過学習しやすい
- **LoRA（Low-Rank Adaptation）**：巨大な行列を直接触らず、横に **2つの小さな行列A（4096×16）とB（16×4096）** を追加する。A×Bの出力が元の行列の出力に足し算される
  - Rank=16の場合、記録する数値は約13万個（1600万個の代わり）
  - これが「低ランク（Low-Rank）」の意味
- **学習中に起きること**：毎ステップ、画像にノイズを加え「このキャプション条件で、このノイズを除去せよ」という課題を解かせる。予測と正解の差（損失）で、小さな行列AとBだけが更新される。ベースモデルの元の行列は凍結されたまま
- **LoRAファイルの正体**：各層のA・Bペアが入っているだけ。ベースモデルが数GBに対し、LoRAが数十〜数百MBで済む理由

### 0-3. 教師あり学習としてのLoRA

LoRA学習は **教師あり学習** に該当する。「画像＋キャプション」のペアが教師データで、「このキャプション条件のもとで、このノイズからこの画像を復元せよ」という明確な正解がある状態で学習する。

### 0-4. 主要パラメータが何を制御しているか

| パラメータ | 制御対象 | 目安 |
|-----------|---------|------|
| Rank（ランク） | 差分行列のサイズ（表現力） | 人物1人：8〜16、スタイル：32〜64 |
| Learning Rate | 毎ステップの重み更新幅 | 1e-4前後が起点 |
| Steps | 学習の反復回数 | 画像枚数×繰り返し回数との兼ね合い |
| Repeats | 1エポックで同じ画像を何回見せるか | 画像が少ない時（10枚以下）は増やす |

---

## 1. データセット品質の最大化

### 1-1. 画像のシャープネス確保

- ピントが甘い・ぼやけた画像は **即除外**。VAEが潜在空間にノイズとして記録してしまう最大要因
- 元画像は **AIアップスケーラー（Real-ESRGAN等）で高画質化** してから学習データにする
- 判断基準：100%表示でエッジがくっきり見えるかどうか
- **PNG等の無圧縮・低圧縮形式で保存**。JPEG圧縮アーティファクトは潜在空間で「意味ある特徴」として誤学習される

### 1-2. 背景の多様性（背景の切り離し）

- 背景が常に同じだと、AIが背景を対象物の一部として誤学習する
- 意図的に背景バリエーションを作る：
  - 白背景（切り抜き風）
  - モデルが手に持っているシーン
  - 机の上に置いたシーン
  - 異なる照明条件
- **対象物だけが共通で、それ以外がバラバラ** な状態が理想

### 1-3. クロップ（切り抜き）で距離感を混ぜる

- 全体像だけでは構造の深い理解ができない
- 以下を混在させる：
  - 全体ショット
  - ロゴ部分のアップ
  - 細部（筆先、テクスチャ等）のクローズアップ
- これによりAIが対象物の **マクロ〜ミクロの構造** を学習できる

---

## 2. キャプション（タグ付け）の設計

### 2-1. Flux向けキャプションの基本（重要）

Fluxは **T5-XXLテキストエンコーダー + CLIP** を使用しており、SD1.5/SDXLのCLIPのみとは根本的に異なる。T5-XXLは自然言語の文構造・文脈を深く理解できる。

- **自然言語（文章形式）でキャプションを書く**。Danbooru風のタグ羅列は最適ではない
- T5-XXLは **文の前半により強い注意を払う傾向がある** ため、学習させたい核心を前に置く

```
# ✅ Flux向き：自然言語キャプション
URDP001 is held horizontally in a person's hand, with the thumb
and fingers clearly visible gripping it. The background is a light
gray wall with natural indoor lighting.

# ❌ Flux向きではない：タグ形式
URDP001, held horizontally, person's hand, thumb visible, gray wall, indoor lighting
```

### 2-2. キャプションの推奨構造（順序が重要）

T5-XXLの注意特性を活かすため、以下の順序でキャプションを構成する：

```
トリガーワード → 人物/対象物の固有特徴（変わらないもの）→ この画像固有の要素（服装、ポーズ、表情）→ 構図・カメラ → ライティング → 背景
```

**この順序が大事な理由**：T5は文の前半により強い注意を払うため、学習させたい核心を前に置くことで、モデルがそこを優先的に条件付けする。

**人物LoRAの例**：
```
ohwx woman, brown eyes, oval face, thin lips, high cheekbones, 
wearing a black turtleneck, standing with arms crossed, looking 
directly at the camera, medium shot from waist up, soft diffused 
lighting from the left, blurred outdoor cafe background.
```

### 2-3. 「引き算」方式のキャプション

最重要テクニック。覚えさせたい対象物 **以外** のすべてをキャプションに記述する。

```
【原理】
キャプションに書かれた要素 → AIは「これは既知の概念だ」と理解し、学習対象から外す
キャプションに書かれていない要素 → AIは「これが新しく覚えるべきものだ」と理解する
```

**具体的なルール**：
- **学習対象の固有特徴は毎回書く**：例えば「brown eyes, oval face, thin lips」のように、全画像で共通する特徴を毎回入れることで、モデルがそれをトリガーワードと強く結びつける
- **画像ごとに変わる要素は正確にその画像の内容を書く**：服が黒なら「black shirt」、白なら「white shirt」。曖昧に「wearing a shirt」とだけ書くと、服の色も人物の固有特徴として学習してしまう
- **主観的・感情的な表現を避ける**：「beautiful」「stunning」「amazing」は情報量ゼロで、推論時にプロンプトを汚染する

**商品LoRAの具体例（まつ毛美容液の場合）：**

```
# ✅ 正しいキャプション例（自然言語形式）
URDP001 is held in a woman's hand with manicured nails against a
white background. The lighting is soft and even, typical of studio
product photography.

# → 手、背景、照明、爪はすべて記述済み
# → 「URDP001」だけが未知の新概念としてAIに学習される
```

```
# ❌ 悪いキャプション例
An eyelash serum beauty product in a cosmetic photo.

# → 曖昧すぎてAIが何を覚えるべきか判断できない
# → "eyelash" "serum" がベースモデルの既存知識と衝突する
```

### 2-4. トリガーワードの設計

- **既存の一般名詞（serum, cream等）をトリガーにしない**
  - ベースモデルが持つ既存知識と衝突・混合してしまう
- **AIが知らないユニークな造語** を使う：
  - 良い例：`URDP001`, `XYZbottle_01`, `ohwx`
  - 悪い例：`serum`, `lash_serum`, `beauty_product`, `UrodaLash`

### 2-5. キャプション作成ワークフロー（Claude Code使用時）

Claude Codeにキャプションを作成させる場合、以下の4点を事前に伝える：

1. **学習目的**：「何を学習させたいのか」（例：特定の人物の顔と体型）
2. **トリガーワード**：使用するトークン（例：`ohwx woman`）
3. **キャプションの構造テンプレート**：セクション2-2の順序
4. **書くべき要素と書かない要素のルール**：セクション2-3の引き算ルール

---

## 3. 正則化画像（Regularization Images）

### 3-1. 正則化画像とは — キャプションと補完する「引き算」の実装手段

「引き算」は設計哲学であり、それを実現する方法は2つある：
- **キャプション側での引き算**（セクション2参照）
- **正則化画像による引き算**（このセクション）

正則化画像は、学習対象を **「含まない」がカテゴリは同じ** 画像。特定の女性を学習するなら「別の女性の画像」を使う。

### 3-2. 学習ループの中で何が起きるか

- 学習画像に対しては「この特徴を覚えろ」と更新される
- 正則化画像に対しては「ベースモデルの元の出力を維持しろ」と引き戻される
- この押し引きで「女性一般の特徴」はベースモデル側に残り、LoRAの差分行列には **その人物だけの固有の差分** だけが記録される

### 3-3. 正則化画像を使わないとどうなるか

モデルが「女性」という概念全体をLoRA側に取り込もうとするため：
- LoRAのウェイトを上げると「全員が同じ顔になる」「ポーズや構図が固定される」
- ウェイトを下げると似なくなる
- 調整幅が極端に狭くなる

### 3-4. 正則化画像の作り方

```
【基本ルール】
- 学習対象のベースモデル自身（Flux.1-dev等）で生成する
  → ベースモデルの潜在空間上の分布と一致させるため
  → 外部写真や別モデルの生成画像を使うと分布がズレて不安定になる
- 学習画像1枚に対して、正則化画像を1〜3枚用意する
- 学習対象と同じ「クラス（形状カテゴリ）」の一般的な画像を使う
```

#### プロンプト例（人物LoRA）

```
# トリガーワードを抜いた、カテゴリレベルのプロンプトで生成
"a woman"
"a woman, portrait"
"a woman, full body"

# 構図は学習画像と似た範囲でばらけさせる
# 学習画像が全部バストアップなら正則化も主にバストアップ
# 全身があるなら全身も混ぜる
# 20〜60枚を生成
```

#### プロンプト例（商品LoRA — ペン型美容液）

```
# 同じ形状カテゴリの一般的な化粧品容器
"A slim pen-shaped cosmetic tube in matte black, lying on a white surface with soft studio lighting."
"A hand holding a slender cylindrical beauty product with a silver cap, against a gray background."
"A small metallic cosmetic pen standing upright on a marble countertop under natural light."

# 重要：学習対象の特徴（ロゴ、特定の色）を含めない
# 30〜40枚を生成
```

### 3-5. 正則化画像のキャプション

- **自然言語の文章形式**でキャプションを付ける
- **トリガーワードは絶対に含めない**（正則化画像は「学習しない側」）
- クラスの一般的な記述にする
- 学習画像と正則化画像のキャプションが似すぎると、LoRAが何も学習しなくなるので注意

### 3-6. 優先順位：キャプション精度が先、正則化は補完

最近のFlux向け学習（特にai-toolkit）では、キャプションの質が高ければ正則化画像なしでも十分な結果が出るケースが増えている。

**推奨フロー**：
1. まずキャプションを徹底的に作り込む
2. それでも概念の混ざりが解消しない場合に正則化画像を導入

---

## 4. ツールキット設定

### 4-1. ai-toolkit（Ostris）— 推奨

Flux LoRA学習で最も広く使われており、Flux対応が早く、コミュニティでの実績が豊富。キャプション精度で概念を分離する方針が主流。

#### 基本的なconfig.yaml例

```yaml
job: extension
config:
  name: "my_flux_lora"
  process:
    - type: sd_trainer
      training_folder: "output"
      device: cuda:0
      trigger_word: "ohwx"
      network:
        type: lora
        linear: 16          # Rank（人物：8〜16、スタイル：32〜64）
        linear_alpha: 16     # 通常はRankと同値
      save:
        dtype: float16
        save_every: 200      # 200ステップごとにスナップショット
      datasets:
        - folder_path: "/path/to/training_images"
          caption_ext: "txt"
          caption_dropout_rate: 0.05
          resolution: [1024]  # Fluxのネイティブ解像度
          batch_size: 1
      train:
        batch_size: 1
        steps: 2000           # 20枚データセットなら1500前後で十分なことが多い
        gradient_accumulation_steps: 1
        train_unet: true
        train_text_encoder: false
        gradient_checkpointing: true
        noise_scheduler: "flowmatch"
        optimizer: "adamw8bit"
        lr: 1e-4              # 商品LoRAは1e-4から。人物は2e-4も可
        ema_config:
          use_ema: true
          ema_decay: 0.99
      model:
        name_or_path: "black-forest-labs/FLUX.1-dev"
        quantize: true        # VRAM節約
      sample:
        sampler: "flowmatch"
        sample_every: 200
        width: 1024
        height: 1024
        prompts:
          - "ohwx woman, portrait, soft lighting"   # 固定プロンプトでプレビュー
        seed: 42
```

### 4-2. kohya_ss（sd-scripts）— 代替手段

sd-scriptsはFlux対応のアップデートをしているが、Flux向けの安定性や情報量でai-toolkitに差をつけられている。SDXLまではkohyaが主流だった。

#### 推奨コマンド（出発点）

```bash
accelerate launch \
  --mixed_precision bf16 \
  --num_cpu_threads_per_process 1 \
  flux_train_network.py \
  --pretrained_model_name_or_path <flux-dev-fp8モデルのパス> \
  --clip_l <clip_lモデルのパス> \
  --ae <VAEモデルのパス> \
  --cache_latents_to_disk \
  --cache_text_encoder_outputs \
  --cache_text_encoder_outputs_to_disk \
  --save_model_as safetensors \
  --sdpa \
  --persistent_data_loader_workers \
  --max_data_loader_n_workers 2 \
  --seed 42 \
  --gradient_checkpointing \
  --mixed_precision bf16 \
  --save_precision bf16 \
  --network_module networks.lora_flux \
  --network_dim 16 \
  --network_alpha 8 \
  --optimizer_type adamw8bit \
  --learning_rate 2e-4 \
  --network_args "loraplus_lr_ratio=16" \
  --lr_scheduler constant_with_warmup \
  --lr_warmup_steps 20 \
  --fp8_base \
  --timestep_sampling shift \
  --discrete_flow_shift 3.1582 \
  --model_prediction_type raw \
  --guidance_scale 1.0 \
  --max_train_steps 2000 \
  --save_every_n_steps 200 \
  --dataset_config <dataset.tomlのパス> \
  --output_dir <出力先パス> \
  --output_name <LoRA名>
```

#### kohya_ss パラメータ解説

| パラメータ | 推奨値 | 説明 |
|-----------|--------|------|
| network_dim | 16〜128 | 16:商品・オブジェクト向き。128:スタイル学習向き |
| network_alpha | dimの半分〜同値 | dim=16ならalpha=8。dim=128ならalpha=64〜128 |
| learning_rate | 1e-4〜2e-4 | 商品LoRAは1e-4から。2e-4で結果が荒れたら下げる |
| optimizer | adamw8bit | VRAM効率良い。Prodigyを使う場合はLR=1.0に設定 |
| loraplus_lr_ratio | 16 | LoRA+の比率。16xが安定した結果を出すと広く報告されている |
| max_train_steps | 1000〜2000 | 20枚データセットなら1500前後で十分なことが多い |
| save_every_n_steps | 200 | 固定seed+固定プロンプトでプレビュー確認用 |
| 解像度 | 1024x1024 | Fluxのネイティブ解像度。512でも動くがクオリティ低下 |
| mixed_precision | bf16 | fp16でも可。bf16が推奨 |

#### dataset.toml の書き方（kohya_ss）

```toml
[general]
shuffle_caption = true
caption_extension = '.txt'
keep_tokens = 1

[[datasets]]
resolution = 1024
batch_size = 1

  [[datasets.subsets]]
  image_dir = '/path/to/training_images'
  num_repeats = 5

  # 正則化画像（推奨）
  [[datasets.subsets]]
  image_dir = '/path/to/regularization_images'
  num_repeats = 1
  is_reg = true
```

**keep_tokens = 1**：キャプションの先頭1トークン（= トリガーワード）をシャッフル対象から除外する設定。トリガーワードが常に先頭に来るようにする。

### 4-3. その他の選択肢

**SimpleTuner**：Flux対応済み、設定の自由度が高いが上級者向け。

---

## 5. 学習中のモニタリングと判断

- **200ステップごとにスナップショット保存** → 固定seed・固定プロンプトでプレビュー
- ステップ600以前にサンプルが急激にシャープになった → **学習率が高すぎる**
- 20枚データセットでステップ1400でもアイデンティティが定着しない → **キャプションか正則化画像に問題**
- **保存ファイル名にメタ情報を含める**：`flux_lora_r16_lr2e-4_s1800_2026-03-28.safetensors`

### Tips

- **1つのLoRAに複数の概念を詰め込まない**：スタイルとサブジェクトを同時に学習させると過学習が速い。小さな単一目的LoRAを複数作ってスタック（重み0.3〜0.6で併用）する方が良い
- **色のバイアスに注意**：データセットが暖色系に偏っているとモデルがそれを増幅する
- **Flux LoRAは1000〜2000ステップで良い結果が出る**ことが多く、Flux以前のモデルより収束が速い

---

## 6. I2V（Image-to-Video）用途のための静止画品質向上

I2Vモデルは最初のフレーム（静止画）の情報量に強く依存する。LoRAで生成する静止画の質がそのまま動画の質を決める。

### 6-1. ライティングと陰影のリッチさ

- フラットな画像よりも、光源がはっきりしていて陰影がある画像のほうが、I2Vモデルが「奥行き」と「動き」を推定しやすい
- キャプションにライティング方向・質感を具体的に記述する（例：`soft diffused lighting from the left`）ことで、推論時に同じ指定で安定した画像を出せるようになる

### 6-2. ディテールの一貫性

- LoRAで生成した画像の手や服のディテールが破綻していると、I2Vはそれを「正しい形状」として動かそうとして崩壊する
- 学習画像の段階でディテールが安定している画像を選別することが重要
- 生成テストの段階で、手・指・衣服の端・アクセサリーの破綻をチェック

### 6-3. キャプション設計とI2Vの関係

キャプションに構図・ポーズ・ライティングを具体的に記述しておくと、推論時にこれらを指定して「I2V向きの画像」を狙って出せるようになる。曖昧なキャプションでは、推論時のプロンプトで構図をコントロールできず、I2Vに適した画像を安定して得られない。

---

## 7. 商品（オブジェクト）LoRA固有の注意事項

### 7-1. 商品LoRAが人物より難しい理由

- 人物は顔・体型・髪型など特徴量が多く、AIが識別しやすい
- 商品（特にボトル・チューブ類）は形状・色・ロゴくらいしか特徴がなく、汎用的な容器との差分が小さい
- そのためキャプションの引き算・正則化画像の精度が人物以上にシビアになる

### 7-2. 正則化画像のクラスを正確に合わせる

正則化画像は学習対象と **同じ形状カテゴリ** である必要がある。

```
# まつ毛美容液（ペン型・マスカラ型）のLoRAの場合：

# ✅ 正しい正則化画像のクラス
- マスカラのような細長いペン型容器
- リップグロスの筆ペン型容器
- 細身のアイライナー型チューブ

# ❌ 間違った正則化画像のクラス
- 太いクリームチューブ（形状が違いすぎる）
- スポイト瓶（全く別カテゴリ）
- 四角いファンデーションボトル（形状が違う）
```

### 7-3. ロゴ再現のためのクロップ戦略

商品LoRAでロゴ・文字の再現性を高めるには、異なるスケールの画像を混ぜる：

```
# 推奨するデータセット構成（20枚の場合）
- 全体ショット（商品全体）: 8〜10枚
- 中間ショット（ロゴ周辺を中心に）: 5〜6枚
- クローズアップ（ロゴ文字、筆先、質感）: 4〜5枚
- 使用シーン（手に持つ、テーブルに置く）: 2〜3枚
```

### 7-4. 反射・透明素材の注意

- メタリック素材（銀色のボトル等）は照明条件で見え方が大きく変わる
- データセットに **異なる照明条件** の画像を必ず含める
- 反射のハイライトが強すぎる画像は、AIがハイライトを「商品の一部」と誤学習するリスクがある
- 透明・半透明の容器は背景と混ざりやすいので、コントラストの高い背景で撮影する

### 7-5. キャプションでの禁止ワード（商品名・用途の記述を避ける）

```
# まつ毛美容液のLoRAの場合、以下はキャプションに書かない：
# eyelash, lash, serum, beauty serum, eye care, cosmetic serum
# → これらがあるとAIが「まつ毛」「目」の概念と混合する

# 代わりにこう書く：
# "a slim silver pen-shaped tube", "a metallic cylindrical container"
# → 形状と素材だけを記述し、用途は言わない
```

---

## 8. 失敗時の修正チェックリスト

既に失敗したデータセットがある場合の立て直し手順：

### Step 1: 画像の選別と強化
- [ ] ぼやけた画像をすべて除外
- [ ] 残った画像をReal-ESRGAN等でアップスケール
- [ ] PNG等の低圧縮形式で保存し直す（JPEGアーティファクトの排除）
- [ ] 背景バリエーションが十分か確認（不足なら追加撮影/収集）
- [ ] クロップバリエーション（全体・中間・アップ）があるか確認

### Step 2: キャプションの再設計
- [ ] 全キャプションが **自然言語の文章形式** であること（タグ形式はNG）
- [ ] キャプション構造が「トリガーワード → 固有特徴 → 画像固有要素 → 構図 → ライティング → 背景」の順序であること
- [ ] 対象物の用途・カテゴリ名（eyelash, serum等）が含まれていないこと
- [ ] ユニークなトリガーワードが各キャプションの先頭にあること
- [ ] 背景・構図・照明など対象物以外の要素がすべて記述されていること
- [ ] 固有特徴が全キャプションで一貫して書かれていること
- [ ] 「beautiful」「stunning」等の主観表現が含まれていないこと

### Step 3: 正則化画像の準備（キャプションで解決しない場合）
- [ ] Flux.1-devで同じ形状カテゴリの一般画像を30〜40枚生成
- [ ] 正則化画像にキャプションを付ける（自然言語、トリガーワードなし）
- [ ] 正則化画像の形状が学習対象と同カテゴリであること（ペン型にはペン型）
- [ ] dataset設定に正則化画像フォルダを追加

### Step 4: 学習設定の見直し
- [ ] 学習率を `1e-4` から開始（商品LoRAの場合）
- [ ] Rank 16、Alpha 8〜16 を設定
- [ ] 200ステップごとにスナップショット保存を有効化
- [ ] まず10〜20枚の少量データセットでテスト学習を実行
- [ ] 固定seed + 固定プロンプトでプレビュー生成して品質確認
- [ ] I2V用途の場合、ライティング指定で安定した画像が出るかテスト
- [ ] 生成テストで品質を確認してから本番学習へ

---

## 9. RunPodでのファイル配置（重要）

### 9-1. Network Volumeにはツールキットやデータセットを置かない

RunPodではNetwork Volume（永続ストレージ）とPodローカルストレージがある。
**ツールキット（ai-toolkit / kohya_ss）、データセット、正則化画像はすべてPodのローカルストレージに配置すること。**

Network Volumeに置くと、学習完了後にLoRAファイルが保存できなくなるトラブルが発生する。

```
# ✅ 正しい配置（Podローカル）
/workspace/ai-toolkit/          # ツールキット本体
/workspace/dataset/             # 学習画像 + キャプション
/workspace/regularization/      # 正則化画像 + キャプション
/workspace/output/              # LoRA出力先

# ❌ 避けるべき配置（Network Volume）
/runpod-volume/ai-toolkit/      # NG：保存トラブルの原因
/runpod-volume/dataset/         # NG
```

### 9-2. Network Volumeの正しい使い方

Network Volumeはモデルファイル（Flux.1-devのチェックポイント等）の保存に使う。モデルは大容量でダウンロードに時間がかかるため、永続ストレージに置いておくのが効率的。

```
# Network Volumeに置くもの
/runpod-volume/models/flux-dev-fp8.safetensors
/runpod-volume/models/clip_l.safetensors
/runpod-volume/models/ae.safetensors

# Podローカルに置くもの
/workspace/ 以下にツールキット、データセット、出力先すべて
```

### 9-3. LoRA完成後の退避

Podを停止・削除するとローカルストレージは消えるため、学習完了後にLoRAファイルをダウンロードするか、Network Volumeにコピーしておく。

```bash
# 学習完了後、LoRAをNetwork Volumeにバックアップ
cp /workspace/output/*.safetensors /runpod-volume/lora_backup/
```

---

## クイックリファレンス

| 項目 | やるべきこと | 避けるべきこと |
|------|-------------|---------------|
| 画像品質 | アップスケール済みのシャープな画像（PNG推奨） | ピントが甘い・ぼやけた画像、JPEG圧縮アーティファクト |
| 背景 | 多様な背景をバラバラに | 同一背景の繰り返し |
| 構図 | 全体・中間・アップを混在 | 同一距離の画像のみ |
| トリガーワード | `URDP001` のような造語 | `serum` 等の一般名詞 |
| キャプション形式 | 自然言語文章、構造化された順序 | タグ形式、順序無視 |
| キャプション内容 | 対象物以外を記述（引き算）、固有特徴は毎回記述 | 対象物の用途を記述、主観表現 |
| 正則化画像 | ベースモデル自身で生成、同形状カテゴリ30〜40枚 | 外部写真、形状が違う画像 |
| 優先順位 | キャプション精度 → 正則化は補完 | 正則化に頼ってキャプションが雑 |
| ツールキット | ai-toolkit（Ostris）推奨 | — |
| 学習率 | 商品は1e-4から開始 | デフォルトのまま放置 |
| 保存 | 200ステップごとにスナップショット | 最終結果のみ保存 |
| I2V用途 | ライティング・構図をキャプションに明記 | フラットな画像、ディテール破綻の放置 |
| テスト | 少量データで先にテスト | 大量データでいきなり本番 |
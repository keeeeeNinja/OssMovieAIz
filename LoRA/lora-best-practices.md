# LoRA作成 ベストプラクティス（Flux.1-dev + kohya_ss）

> このドキュメントはClaude Codeに読ませて、LoRA学習の設計・トラブルシュート時に参照するためのリファレンスです。
> 対応ツール：kohya_ss（sd-scripts）
> 対応モデル：Flux.1-dev

---

## 核心原則

LoRA学習の本質は **「AIに何を覚えさせ、何を忘れさせるか」を緻密にコントロールすること** である。数より質、そして「引き算」の設計思想が成功の鍵。

---

## 1. データセット品質の最大化

### 1-1. 画像のシャープネス確保

- ピントが甘い・ぼやけた画像は **即除外**。学習にノイズを持ち込む最大要因
- 元画像は **AIアップスケーラー（Real-ESRGAN等）で高画質化** してから学習データにする
- 判断基準：100%表示でエッジがくっきり見えるかどうか

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

Fluxは**T5-XXLテキストエンコーダー**を使用しており、SD1.5/SDXLのCLIPとは根本的に異なる。

- **自然言語（文章形式）でキャプションを書く**。Danbooru風のタグ羅列は最適ではない
- T5-XXLは文の構造・文脈を理解できるため、文章の方が意味を正確に伝えられる

```
# ✅ Flux向き：自然言語キャプション
URDP001 is held horizontally in a person's hand, with the thumb
and fingers clearly visible gripping it. The background is a light
gray wall with natural indoor lighting.

# ❌ Flux向きではない：タグ形式
URDP001, held horizontally, person's hand, thumb visible, gray wall, indoor lighting
```

### 2-2. 「引き算」方式のキャプション

最重要テクニック。覚えさせたい対象物 **以外** のすべてをキャプションに記述する。

```
【原理】
キャプションに書かれた要素 → AIは「これは既知の概念だ」と理解し、学習対象から外す
キャプションに書かれていない要素 → AIは「これが新しく覚えるべきものだ」と理解する
```

**具体例（まつ毛美容液の場合）：**

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

### 2-3. トリガーワードの設計

- **既存の一般名詞（serum, cream等）をトリガーにしない**
  - ベースモデルが持つ既存知識と衝突・混合してしまう
- **AIが知らないユニークな造語** を使う：
  - 良い例：`URDP001`, `XYZbottle_01`
  - 悪い例：`serum`, `lash_serum`, `beauty_product`, `UrodaLash`

### 2-4. タグ付けワークフロー（Flux向け）

1. 各画像の内容を**自然言語の文章**で記述する
2. 文章の先頭にトリガーワードを配置する
3. 対象物の**用途・カテゴリ名は書かない**（形状と素材だけ記述）
4. 手、背景、照明、構図など対象物以外の要素をすべて記述する

---

## 3. kohya_ss Flux LoRA推奨パラメータ

### 3-1. 推奨コマンド（出発点）

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

### 3-2. パラメータ解説

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

### 3-3. dataset.toml の書き方

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

### 3-4. 判断の目安（学習中のモニタリング）

- **200ステップごとにスナップショット保存** → 固定seed・固定プロンプトでプレビュー
- ステップ600以前にサンプルが急激にシャープになった → **学習率が高すぎる**
- 20枚データセットでステップ1400でもアイデンティティが定着しない → **キャプションか正則化画像に問題**
- **保存ファイル名にメタ情報を含める**：`flux_lora_r16_lr2e-4_s1800_2026-03-28.safetensors`

### 3-5. その他のTips

- **1つのLoRAに複数の概念を詰め込まない**：スタイルとサブジェクトを同時に学習させると過学習が速い。小さな単一目的LoRAを複数作ってスタック（重み0.3〜0.6で併用）する方が良い
- **色のバイアスに注意**：データセットが暖色系に偏っているとモデルがそれを増幅する
- **Flux LoRAは1000〜2000ステップで良い結果が出る**ことが多く、Flux以前のモデルより収束が速い

---

## 4. 正則化画像（Regularization Images）

### 4-1. 正則化画像とは

正則化画像は、LoRA学習時に **「学習対象以外のベースモデルの能力を保護する」** ための画像。キャプションの「引き算」方式と補完関係にあり、併用すると効果が大きい。

### 4-2. なぜ必要か

- LoRA学習はベースモデルの重みを部分的に変更する
- 正則化画像なしだと、学習対象に引っ張られてベースモデルの汎用能力が壊れる
- 例：美容液LoRAを学習すると、全く関係ない「ボトル」のプロンプトにも美容液の特徴が漏れ出す

### 4-3. 正則化画像の作り方

```
【基本ルール】
- 学習画像1枚に対して、正則化画像を1〜3枚用意する
- 学習対象と同じ「クラス（形状カテゴリ）」の一般的な画像を使う
- Flux.1-dev自身で生成するのが最も相性が良い
```

#### オブジェクト（商品）LoRAの場合

```
# 美容液（ペン型）のLoRAなら：
# 正則化画像 = 同じ形状の一般的な化粧品容器
# プロンプト例（自然言語）：
"A slim pen-shaped cosmetic tube in matte black, lying on a white surface with soft studio lighting."
"A hand holding a slender cylindrical beauty product with a silver cap, against a gray background."
"A small metallic cosmetic pen standing upright on a marble countertop under natural light."

# 重要：学習対象の特徴（ロゴ、特定の色）を含めない
```

#### 人物（アイデンティティ）LoRAの場合

```
# 正則化画像 = 一般的な「人物」の画像
# プロンプト例：
"A photo of a person with a neutral expression, standing against a plain background in natural light."

# 20〜60枚の正則化画像をFlux.1-devで生成
```

### 4-4. 正則化画像のキャプション

- 正則化画像にも**自然言語の文章形式**でキャプションを付ける
- **トリガーワードは絶対に含めない**（正則化画像は「学習しない側」）
- クラスの一般的な記述にする
- 学習画像と正則化画像のキャプションが似すぎると、LoRAが何も学習しなくなるので注意

### 4-5. kohya_ssでの設定方法

dataset.toml内で `is_reg = true` を指定する（セクション3-3の例を参照）。

---

## 5. 商品（オブジェクト）LoRA固有の注意事項

### 5-1. 商品LoRAが人物より難しい理由

- 人物は顔・体型・髪型など特徴量が多く、AIが識別しやすい
- 商品（特にボトル・チューブ類）は形状・色・ロゴくらいしか特徴がなく、汎用的な容器との差分が小さい
- そのためキャプションの引き算・正則化画像の精度が人物以上にシビアになる

### 5-2. 正則化画像のクラスを正確に合わせる

正則化画像は学習対象と**同じ形状カテゴリ**である必要がある。

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

### 5-3. ロゴ再現のためのクロップ戦略

商品LoRAでロゴ・文字の再現性を高めるには、異なるスケールの画像を混ぜる：

```
# 推奨するデータセット構成（20枚の場合）
- 全体ショット（商品全体）: 8〜10枚
- 中間ショット（ロゴ周辺を中心に）: 5〜6枚
- クローズアップ（ロゴ文字、筆先、質感）: 4〜5枚
- 使用シーン（手に持つ、テーブルに置く）: 2〜3枚
```

### 5-4. 反射・透明素材の注意

- メタリック素材（銀色のボトル等）は照明条件で見え方が大きく変わる
- データセットに**異なる照明条件**の画像を必ず含める
- 反射のハイライトが強すぎる画像は、AIがハイライトを「商品の一部」と誤学習するリスクがある
- 透明・半透明の容器は背景と混ざりやすいので、コントラストの高い背景で撮影する

### 5-5. キャプションでの禁止ワード（商品名・用途の記述を避ける）

```
# まつ毛美容液のLoRAの場合、以下はキャプションに書かない：
# eyelash, lash, serum, beauty serum, eye care, cosmetic serum
# → これらがあるとAIが「まつ毛」「目」の概念と混合する

# 代わりにこう書く：
# "a slim silver pen-shaped tube", "a metallic cylindrical container"
# → 形状と素材だけを記述し、用途は言わない
```

---

## 6. 失敗時の修正チェックリスト

既に失敗したデータセットがある場合の立て直し手順：

### Step 1: 画像の選別と強化
- [ ] ぼやけた画像をすべて除外
- [ ] 残った画像をReal-ESRGAN等でアップスケール
- [ ] 背景バリエーションが十分か確認（不足なら追加撮影/収集）
- [ ] クロップバリエーション（全体・中間・アップ）があるか確認

### Step 2: キャプションの再設計
- [ ] 全キャプションが**自然言語の文章形式**であること（タグ形式はNG）
- [ ] 対象物の用途・カテゴリ名（eyelash, serum等）が含まれていないこと
- [ ] ユニークなトリガーワードが各キャプションの先頭にあること
- [ ] 背景・構図・照明など対象物以外の要素がすべて記述されていること

### Step 3: 正則化画像の準備
- [ ] Flux.1-devで同じ形状カテゴリの一般画像を30〜40枚生成
- [ ] 正則化画像にキャプションを付ける（自然言語、トリガーワードなし）
- [ ] 正則化画像の形状が学習対象と同カテゴリであること（ペン型にはペン型）
- [ ] dataset.tomlに `is_reg = true` で追加

### Step 4: 学習設定の見直し
- [ ] 学習率を `1e-4` から開始（商品LoRAの場合）
- [ ] `--network_dim 16 --network_alpha 8` を設定
- [ ] `--network_args "loraplus_lr_ratio=16"` を追加
- [ ] `--save_every_n_steps 200` でスナップショット保存を有効化
- [ ] まず10〜20枚の少量データセットでテスト学習を実行
- [ ] 固定seed + 固定プロンプトでプレビュー生成して品質確認
- [ ] 生成テストで品質を確認してから本番学習へ

---

## 7. RunPodでのファイル配置（重要）

### 7-1. Network Volumeにはツールキットやデータセットを置かない

RunPodではNetwork Volume（永続ストレージ）とPodローカルストレージがある。
**ツールキット（kohya_ss）、データセット、正則化画像はすべてPodのローカルストレージに配置すること。**

Network Volumeに置くと、学習完了後にLoRAファイルが保存できなくなるトラブルが発生する。

```
# ✅ 正しい配置（Podローカル）
/workspace/kohya_ss/           # ツールキット本体
/workspace/dataset/            # 学習画像 + キャプション
/workspace/regularization/     # 正則化画像 + キャプション
/workspace/output/             # LoRA出力先

# ❌ 避けるべき配置（Network Volume）
/runpod-volume/kohya_ss/       # NG：保存トラブルの原因
/runpod-volume/dataset/        # NG
```

### 7-2. Network Volumeの正しい使い方

Network Volumeはモデルファイル（Flux.1-devのチェックポイント等）の保存に使う。モデルは大容量でダウンロードに時間がかかるため、永続ストレージに置いておくのが効率的。

```
# Network Volumeに置くもの
/runpod-volume/models/flux-dev-fp8.safetensors
/runpod-volume/models/clip_l.safetensors
/runpod-volume/models/ae.safetensors

# Podローカルに置くもの
/workspace/ 以下にツールキット、データセット、出力先すべて
```

### 7-3. LoRA完成後の退避

Podを停止・削除するとローカルストレージは消えるため、学習完了後にLoRAファイルをダウンロードするか、Network Volumeにコピーしておく。

```bash
# 学習完了後、LoRAをNetwork Volumeにバックアップ
cp /workspace/output/*.safetensors /runpod-volume/lora_backup/
```

---

## クイックリファレンス

| 項目 | やるべきこと | 避けるべきこと |
|------|-------------|---------------|
| 画像品質 | アップスケール済みのシャープな画像 | ピントが甘い・ぼやけた画像 |
| 背景 | 多様な背景をバラバラに | 同一背景の繰り返し |
| 構図 | 全体・中間・アップを混在 | 同一距離の画像のみ |
| トリガーワード | `URDP001` のような造語 | `serum` 等の一般名詞 |
| キャプション | 自然言語文章で対象物以外を記述 | タグ形式、対象物の用途を記述 |
| 学習率 | 商品は1e-4から開始 | デフォルトのまま放置 |
| LoRA+ | `loraplus_lr_ratio=16` を使用 | LoRA+なしで学習 |
| 保存 | 200ステップごとにスナップショット | 最終結果のみ保存 |
| 正則化画像 | 同形状カテゴリの一般画像を30〜40枚 | 形状が違う画像、または正則化なし |
| テスト | 少量データで先にテスト | 大量データでいきなり本番 |

---
name: flux-image
description: bs分析＋plan-video構成案から各シーンのFlux用静止画プロンプトを生成し、RunPod Serverless で一括生成する。「静止画作って」「プロンプト作って」「flux-image」「画像生成して」「Step 6」という場面で使う。
allowed-tools: Read, Write, Bash(*), Grep, Glob
---

## Flux静止画プロンプト生成＋一括生成スキル

bs分析のカット構成とplan-videoの構成案をベースに、各シーンのFlux向けプロンプトを自動生成し、RunPod Serverless（`scripts/serverless_request.py --endpoint flux`）で一括生成する。

---

### Step 1: 前提情報を収集する

#### 1-1. bs分析結果を確認する

制作フローStep 2で実行済みのbs分析結果から以下を取得する：
- **各カットのrole**（hook / main / cta）
- **各カットのcamera_work**（ショットサイズの参考）
- **各カットのtone / mood**（ライティング・雰囲気の参考）

bs分析結果がまだない場合は「先にbs分析（Step 2）を実行してください」と伝えて終了する。

#### 1-2. plan-video構成案を確認する

`作業中動画/プロンプト.md` を読み、Step 4で確定した構成案を取得する：
- **シーン数・各シーンの秒数・役割**
- **各シーンのカメラワーク指定**
- **各シーンの推奨エンジン**

構成案がまだない場合は「先に `/plan-video`（Step 4）を実行してください」と伝えて終了する。

#### 1-3. ユーザーに確認する（2つだけ）

以下をユーザーに聞く：

1. **テーマ**: 「この動画のテーマを教えてください（例：まつ毛美容液、カフェ紹介など）」
2. **使用LoRA**: 「使用するLoRAを教えてください（例：flux_japanese_girl_v2.safetensors）。使わない場合は「なし」で。」

※ トリガーワードはLoRAファイル名とRunPod上のLoRA情報から自動で決定する。ユーザーには聞かない。

---

### Step 2: トリガーワードを決定する

LoRAを使用する場合、以下の手順でトリガーワードを特定する：

1. LoRAファイル名からトリガーワードを推定する
   - 例: `flux_japanese_girl_v2.safetensors` → `ohwx woman`（Fluxの人物LoRAで最も一般的）
   - 例: `extra_long_lashes.safetensors` → LoRA名から推定
2. 過去の `scripts/flux_prompts.json` にトリガーワードの使用例がある場合はそれを参考にする
3. LoRAファイルは Network Volume の `/workspace/ComfyUI/models/loras/` に配置されている前提（Serverless ワーカーがマウントして参照する）。存在確認は `LoRA/` ディレクトリのローカルコピーを Glob で見るか、過去 `flux_prompts.json` の使用実績で代用する

決定したトリガーワードは各プロンプトの先頭に付与する。

---

### Step 3: シーンごとのプロンプトを生成する

#### 3-1. bs分析からの導出ルール

| bs分析の要素 | プロンプトへの変換 |
|-------------|-----------------|
| `camera_work: rapid_dolly_in` | → extreme close-up shot |
| `camera_work: static` | → medium shot |
| `camera_work: slow_zoom_in` | → close-up shot |
| `camera_work: zoom_out` | → wide establishing shot |
| `camera_work: pan` | → medium wide shot |
| `cut.role: hook` | → dramatic lighting, bold composition |
| `cut.role: main` | → clean lighting, product showcase |
| `cut.role: cta` | → warm inviting atmosphere |
| `asset.tone: warm` | → warm soft lighting |
| `asset.tone: cool` | → cool blue-toned lighting |
| `asset.tone: dramatic` | → high contrast dramatic lighting |

#### 3-2. Flux向けプロンプトフォーマット

**必須ルール：**
- **英語のみ**（日本語は絶対に入れない）
- **カンマ区切りのフレーズ**（文章ではない）
- **1プロンプト ≤ 77トークン（約100語）を目安にする**（CLIPの制約。超えると後半が無視される）
- **ネガティブプロンプトは使わない**（Fluxはネガティブ非対応）

**プロンプト構造（この順序で記述）：**

```
[トリガーワード], [被写体の動作・ポーズ], [表情], [衣装・服装], [背景・ロケーション], [ライティング], [カメラアングル・ショットサイズ], [画風・品質タグ]
```

**各要素の指針：**

| 要素 | 指針 |
|------|------|
| トリガーワード | LoRA使用時のみ先頭に付与（例: `ohwx woman`） |
| 動作・ポーズ | 具体的に（`holding a serum bottle near her face` ✓ / `posing` ✗） |
| 表情 | 簡潔に（`gentle smile`, `surprised expression`） |
| 衣装 | シーンに合った具体的な服装（`casual white top`, `silk blouse`） |
| 背景 | 具体的なロケーション（`clean white studio`, `modern bathroom`） |
| ライティング | bs分析のtoneから導出（`soft natural side lighting`, `warm studio lighting`） |
| ショットサイズ | bs分析のcamera_workから導出（Step 3-1参照） |
| 品質タグ | `photorealistic, 8K, ultra sharp, commercial photography` を基本とする |

**書かないこと（LoRAが担保する要素）：**
- 顔の造形（骨格、輪郭、パーツの形）
- 髪色・髪型の詳細
- 目の色
- 肌の質感の詳細
- 年齢の具体的数値

**人物以外のカット（商品写真など）の場合：**
- トリガーワードを付けない
- `product photo of ...` で始める
- `professional product photography` を品質タグに使う

---

#### 3-3. I2V前提のプロンプト設計ガイドライン（必須）

**この静止画はWan 2.1 I2Vで動かす「動画の最初のフレーム」である。** 単体で完成した写真ではない。以下の4点を必ず守ること。

1. **ポーズ設計 — 動きの余白を残す**
   - I2Vが自然に動かせる静的ポーズを選ぶ
   - 動詞の途中動作は避ける:
     - ✗ `applying serum` / `walking` / `leaning in` / `raising hand`
     - ✓ `holding serum wand close to upper lashes` / `standing on sidewalk with head slightly lowered` / `sitting beside her friend` / `hand resting on table`
   - 腕を大きく広げたり極端なポーズ、ジャンプ、複雑な相互作用は避ける
   - 「今にも動き出しそう」な自然な静止姿勢にする

2. **構図設計 — カメラワークの余白を確保する**
   - 顔・被写体がフレームギリギリにならないよう、少し引きの構図にする
   - `extreme close-up` は I2V で寄る余地がないので、push-in が入る場合は `medium close-up` 程度に留める
   - 頭上・左右に一定の余白を残し、push-in / pan / tilt のどれが入っても破綻しないようにする

3. **表情設計 — 控えめに、I2Vで感情を足す前提**
   - 大げさな表情タグは使わない:
     - ✗ `amazed surprised expression` / `troubled melancholic` / `bright radiant smile` / `defeated exhausted`
     - ✓ `quiet subtle expression` / `soft gentle smile` / `calm neutral face` / `slightly tired look`
   - I2Vで表情の推移（目を開く・微笑み始める等）を後付けするため、1フレーム目はニュートラル寄りにする

4. **シーン間のつながり — 前後カットと整合させる**
   - 直前・直後のシーンと人物の向き・服装・ロケーション・ライティングを矛盾させない
   - 同一人物のカットが続く場合、視線の向き・体の向きが180度反転しないよう配慮する（180度ルール）
   - 服装は1動画内で原則同じ（シーン間に時間経過を示したいときのみ変更し、プロンプト.mdに明記）

**自己チェック（プロンプト作成後に必ず確認）:**
- [ ] 動詞 `-ing` で進行中の動作を書いていないか
- [ ] `extreme close-up` でpush-inの余地を潰していないか
- [ ] 表情が強すぎないか（Fluxが固まった瞬間を出力してもI2Vで感情を足せる範囲か）
- [ ] 前後シーンと服装・ロケーション・ライティングが連続しているか

---

### Step 4: flux_prompts.jsonに保存する

以下の形式で保存する：

```json
[
  {
    "id": "C01",
    "prompt": "ohwx woman, looking into bathroom mirror with troubled expression, ..."
  },
  {
    "id": "C02",
    "prompt": "ohwx woman, holding smartphone and smiling, ..."
  }
]
```

保存先: `scripts/flux_prompts.json`

**idの命名ルール：**
- **単一テーマ**: `C01`, `C02`, ... と連番
- **マルチテーマ**: `T1_C01`, `T2_C01`, `T3_C01` のようにテーマプレフィックス付き。全テーマを1ファイルに混在させ、Step 5 の生成時に `--scenes` でフィルタする
- plan-videoのScene番号に対応させる

保存後、ユーザーにプロンプト一覧を提示して確認を求める。

---

### Step 5: 画像を生成する（Serverless）

ユーザーの承認後、`scripts/serverless_request.py --endpoint flux` を `run_in_background: true` で実行する。Pod 起動・SSH 接続は不要。

#### 5-1. 前提

- `~/.zshrc` に `RUNPOD_API_KEY` が設定済み（環境変数として読まれる）
- `.env` に `RUNPOD_ENDPOINT_FLUX` が設定済み（`load_dotenv` で自動ロード）
- LoRA を使う場合、Network Volume（Serverless ワーカーが自動マウント）の `models/loras/` に該当ファイルが存在すること

#### 5-2. 実行コマンド

```bash
python3 scripts/serverless_request.py \
  --endpoint flux \
  --prompts scripts/flux_prompts.json \
  --output-root 作業中動画 \
  --lora <LoRAファイル名> \
  --lora-strength 0.85 \
  --width 768 --height 1280 \
  --steps 25 \
  --save-locally
```

- LoRA 不使用の場合は `--lora` 省略（テンプレが `flux.json`、付与時は `flux_lora.json` に切り替わる）
- `Ayano_Chan` 系 LoRA は自動で strength=0.85 になる（スクリプト内ロジック）
- `--save-locally` で完了 job の `output.images[*].data` を base64 デコードして `作業中動画/theme{N}/` に保存する
- `--output-root 作業中動画` を指定すると id の `T{N}_` プレフィックスから theme フォルダへ自動振り分け
- マルチテーマも単一テーマも同じコマンド。プロンプト JSON に `T1_C01` / `T2_C01` などを混在させれば一括投入される
- 並列実行は Serverless 側のワーカープールが裁く。ローカル側のロック（`作業中動画/.locks_serverless_flux/`）は同じ id を二重投入しないためだけのもの

#### 5-3. 生成結果を確認する（クオリティゲート）

生成された画像を**全枚**Readツールで読み込み、ユーザーに一覧を提示する。
以下を確認し、NGがあればプロンプト修正→再生成してからStep 6に進む：

- 構図・ポーズが意図通りか
- 背景・ライティングがプロンプトと合っているか
- LoRA適用時は顔の一貫性が保たれているか

「画像を確認してください。NGがあれば指摘してください。問題なければ「はい」と言ってください。」と伝えて**必ず待機する**。

> **重要:** ここで問題を見逃すとWan生成（1クリップ約3分）のGPU時間が無駄になる。静止画の再生成は数秒で済むので、ここで確実にOKを取る。

---

### Step 6: 完了報告

```
静止画の生成が完了しました。
生成結果: 作業中動画/flux_C01.png 〜 flux_CXX.png

次のステップ:
- クリップ生成に進む場合は /wan-video を使ってください
```

---

### 注意点

- **プロンプトは短く具体的に**。長い説明文よりカンマ区切りのキーワードが効く
- **Fluxは77トークン制限がある**。品質タグを入れても100語を超えないようにする
- **同じLoRAでも強度で出力が変わる**。デフォルト0.85で、必要に応じて調整
- **人物カットと商品カットでLoRA使用を分けたい場合は、別の `flux_prompts.json` を 2 系統に分けて 2 回実行する**（Serverless ルートでは 1 回の呼び出しで LoRA on/off 切り替えはできない）
- **再生成したい場合は `作業中動画/.locks_serverless_flux/<id>.lock` を削除してから実行する**（同 id の二重投入はロックでブロックされる）

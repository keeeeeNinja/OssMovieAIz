---
name: wan-video
description: 作業中動画フォルダの画像を分析してWan 2.1 I2V（ComfyUI on RunPod）用のプロンプトを作成し、SSH経由でRunPodに送信して動画生成まで実行する。Wanで動画作って、Wan用プロンプト、ComfyUIで生成、RunPodで動画生成して、という場面で必ず使う。
allowed-tools: Bash(ls *), Bash(ssh *), Bash(scp *), Bash(sleep *), Bash(curl *), Read, Write
---

## Wan 2.1 I2V 動画生成（ComfyUI on RunPod）

`作業中動画/` 内の画像を分析し、Wan 2.1 Image-to-Videoに最適な英語プロンプトを生成してRunPodのComfyUI APIで動画生成まで実行する。

---

### 設計思想

プロンプトは技術指示ではなく「視聴者体験の設計図」である。

```
① 視聴者体験の設計（何を感じさせたいか）
　↓
② シーンごとの目的と視聴者の感情を定義
　↓
③ 各要素の「見せ方上の役割」を決める
　↓
④ 技術指示に変換する（プロンプト文言・カメラ・ステップ数）
```

**技術制約は「視聴者体験を諦める理由」にならない。** Wan 2.1の制約（1画像入力のみ・480p等）は乗り越えるべき障壁であり、体験の設計を変える理由ではない。

---

### Step 0: RunPod接続情報を確認する

生成を実行するにはRunPodへのSSH接続が必要。以下を確認する:

1. `pod起動コマンド.md` を読んでPodの起動方法を確認する
2. ユーザーに「RunPodのPodは起動していますか？ SSH接続先（IP・ポート）を教えてください」と聞く
3. 接続情報を受け取ったらSSHで疎通確認する:

```bash
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@[IP] -p [PORT] -i ~/.ssh/id_ed25519 "echo connected && nvidia-smi | head -3"
```

疎通できたらStep 1へ進む。接続できない場合はユーザーに報告して停止。

**以降、`SSH_HOST`=`root@[IP] -p [PORT] -i ~/.ssh/id_ed25519` と表記する。実行時は実際の値に置き換える。**

---

### Step 1: 画像ファイルを確認する

```
ls /Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/
```

画像ファイル（.png / .jpg / .jpeg / .webp）をリストアップする。0枚なら「作業中動画フォルダに画像が見つかりません」と伝えて終了。

---

### Step 2: 画像を読み込んで内容を把握する

すべての画像を Read ツールで読み込む。以下を把握する:

- **何が写っているか**（商品・人物・背景・小道具）
- **雰囲気・テイスト**（高級感/カジュアル/清潔感/可愛い等）
- **広告のターゲットと目的**（誰に何を伝えたい動画か）
- **登場する被写体の種類と数**（商品のみ / 人物のみ / 商品+人物）

---

### Step 3: 視聴者体験を設計する

技術的なことを考える前に、まず「動画を見た人がどう感じるか」を設計する。

#### 3-1. 視聴者の感情フローを定義する

各シーンで視聴者に「何を感じさせたいか」を1行で書く。

**典型的な広告の感情フロー例:**

```
パターンA: 商品→人物→商品（王道）
  Scene1: 「何これ？」 → 商品への興味・好奇心
  Scene2: 「こうなりたい」 → 使用者への憧れ
  Scene3: 「欲しい」 → 商品への購買意欲

パターンB: 困り→解決→商品（問題解決型）
  Scene1: 「わかる…」 → 悩みへの共感
  Scene2: 「すごい」 → 解決の驚き
  Scene3: 「これで解決できるんだ」 → 商品への信頼
```

#### 3-2. 各シーンの「視線の主役」を決める

**視聴者がそのシーンで一番見ているもの**を明確にする。

⚠️ 広告全体の主役（＝商品）と、各シーンの視線の主役は異なることがある。それは広告構成として正しい。

#### 3-3. Wan 2.1 I2V固有の制約との照合

視聴者体験の設計が決まったら、Wanの制約と照合する。

**Wan 2.1 I2V の重要制約:**
- 1シーン＝1画像のみ入力（Image-to-Video）
- 出力解像度は480p（832×480 or 480×832）
- 出力尺は約5秒（81フレーム）
- GGUFモデル（Q5_K_M量子化）のためフルモデルより少し品質が落ちる
- 人物の細かい手指の動きは苦手（AI動画共通の弱点）

⚠️ 制約があっても体験の設計を諦めない。制約を乗り越える方法を考える。

ユーザーにこの設計を提示して確認を得てから Step 4 に進む。

---

### Step 4: 動画構成をユーザーと確認する

以下をまとめてユーザーに聞く:

1. **シーン数**: 何本のクリップを作るか（通常3本）
2. **各シーンのコンセプト**: Step 3 の感情フローをベースに提案する
3. **各シーンの参照画像**: どの画像をどのシーンに使うか

ユーザーの回答を受けてから Step 5 に進む。

---

### Step 5: プロンプトを生成する

#### Wan 2.1 I2V プロンプト設計の基本方針

**参照画像ありき**: 視覚スタイルは参照画像が担う。プロンプトは「動き」と「カメラ」と「雰囲気」だけを指定する。

**英語で書く**: ComfyUI + Wanへのプロンプトは英語が最も安定する。

**縦型動画**: 解像度は `480×832`（9:16縦型）。横型なら `832×480`。

#### 動き指定の原則

**前提：技術制約は「視聴者体験を諦める理由」にならない**

Wan 2.1はKlingやRunwayと比べると動きのコントロール精度が低い（オープンソースモデルの特性）。しかしそれは「できないこと」ではなく「シンプルに書くべき」ということ。

**Wan 2.1 I2Vの動き特性:**
- 参照画像の構図をかなり忠実に維持する（I2Vの強み）
- 大きな動きよりも微細な動き（髪の揺れ・瞬き・光の変化）が得意
- カメラワークの指示が比較的効きやすい
- 複雑な動詞の組み合わせは無視されやすい → シンプルに1〜2アクション

**動き・接触のコントロール戦略:**

| 視聴者体験の要求 | コントロール戦略 |
|---------------|--------------|
| 動きが体験の核心（食べる・使うなど） | 動詞を1つだけ使い、修飾語で抑制する。Wan 2.1 は接触を不安定に描く傾向があるので結果の状態で補強 |
| 動きはあるが体験の核心ではない | 「結果の状態」で表現する |
| 動きなしで体験が成立する | 状態のみ指定。カメラで動きを演出する |

**動詞 vs 状態の使い分け例:**

| 動詞指定（不安定になりやすい） | 状態指定（安定） |
|--------------------------|--------------|
| `eats the dessert` | `enjoying the moment, fork resting on the plate` |
| `reaches for the product` | `her hand resting near the product` |
| `lifts the product` | `the product placed elegantly on the table` |
| `walks forward` | `standing gracefully, slight breeze in hair` |

**カメラワーク（Wan 2.1で効きやすい指示）:**
- `slow push-in`（ゆっくり寄る・商品の魅力を引き出す）
- `slow pull-back`（ゆっくり引く・全体を見せる）
- `camera slowly orbits`（旋回・シネマティック感）
- `gentle tilt down`（上から商品へ）
- `static shot, subtle movement`（固定カメラ・被写体の微細な動き）

#### プロンプトテンプレート

**商品のみ:**
```
[商品の状態・配置]. [光の演出]. [カメラワーク]. [雰囲気キーワード], high quality, 4K.
```

**人物のみ / 人物メイン:**
```
[人物の状態・ポーズ・表情]. [商品または小道具の配置（状態で）]. [カメラワーク]. [光・雰囲気], high quality, 4K.
```

**Wan 2.1用の品質ブースト接尾辞（常に付ける）:**
```
, high quality, cinematic lighting, detailed, 4K
```

**ネガティブプロンプト（常に使用）:**
```
blurry, distorted, low quality, shaky, deformed hands, extra fingers, watermark, text overlay
```

---

### Step 6: プロンプト.mdに保存する

`/Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/プロンプト.md` に書き出す（上書き）。

**出力フォーマット:**

```markdown
# [案件名] Wan 2.1 I2Vプロンプト（ComfyUI on RunPod）

> 基本方針: 視聴者体験を設計してから技術指示に落とし込む。

---

## 視聴者体験設計

| シーン | 視聴者の感情 | 視線の主役 |
|-------|------------|-----------|
| Scene 1 | [感情] | [主役] |
| Scene 2 | [感情] | [主役] |
| Scene 3 | [感情] | [主役] |

---

## Scene 1 — [コンセプト名]（5秒）

**参照画像:** `[ファイル名]`
**モデル:** Wan 2.1 I2V 14B (Q5_K_M GGUF)
**解像度:** 480×832（縦型9:16）
**ステップ数:** 30
**CFG:** 1.0

**プロンプト（英語）**
```
[プロンプト本文]
```

**ネガティブプロンプト:**
```
blurry, distorted, low quality, shaky, deformed hands, extra fingers, watermark, text overlay
```

**視聴者体験:** [このシーンで何を感じさせるか]
**動きの指示:** [日本語で1行の動き説明]

---

## Scene 2 — ...

（以下同様）
```

保存後、プロンプト内容をユーザーに提示し、**ここで必ず止まる**。

「プロンプトを保存しました。修正があればお知らせください。問題なければ「生成して」と言ってください。」と伝えて待機する。

---

### Step 7: 生成指示を受けてから進む

ユーザーから「生成して」「OK」「このまま進めて」などの明示的な指示を受けてから Step 8 に進む。

プロンプトの修正を求められた場合は `プロンプト.md` を編集して再度ユーザーに提示し、再度待機する。

---

### Step 8: ComfyUIが起動しているか確認する

```bash
ssh -o StrictHostKeyChecking=no SSH_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:8188/"
```

- `200` → 起動済み。Step 9 へ進む。
- それ以外 → ComfyUIを起動する:

```bash
ssh -o StrictHostKeyChecking=no SSH_HOST "cd /workspace/ComfyUI && nohup python3 main.py --listen 0.0.0.0 --port 8188 > /workspace/comfyui.log 2>&1 & echo starting"
```

30秒待ってから再確認。起動しなければ `comfyui.log` を読んでユーザーに報告。

---

### Step 9: 参照画像をRunPodにアップロードする

各シーンの参照画像を `scp` でRunPodにアップロードする。

```bash
scp -o StrictHostKeyChecking=no -P [PORT] -i ~/.ssh/id_ed25519 \
  "/Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/[ファイル名]" \
  root@[IP]:/workspace/ComfyUI/input/[ファイル名]
```

- 同じ画像を複数シーンで使う場合は1回だけアップロードする
- アップロード後に存在確認: `ssh SSH_HOST "ls -lh /workspace/ComfyUI/input/[ファイル名]"`

---

### Step 10: ComfyUI APIでワークフローを実行する

各シーンごとにComfyUI APIにワークフローJSONを送信する。

#### Wan 2.1 I2V ワークフローJSON

以下のJSONテンプレートを使う。`[PROMPT]`、`[NEGATIVE]`、`[IMAGE_NAME]`、`[OUTPUT_PREFIX]`、`SEED_VALUE` を各シーンの値に置き換える。

**解像度切り替え:**
- 縦型480p: `width=480, height=832, coefficients="i2v_480"`
- 縦型720p: `width=720, height=1280, coefficients="i2v_720"`

```bash
ssh -o StrictHostKeyChecking=no SSH_HOST 'python3 -c "
import json, urllib.request

workflow = {
  \"1\": {
    \"class_type\": \"UnetLoaderGGUF\",
    \"inputs\": {
      \"unet_name\": \"wan2.1-i2v-14b-480p-Q5_K_M.gguf\"
    }
  },
  \"2\": {
    \"class_type\": \"CLIPLoader\",
    \"inputs\": {
      \"clip_name\": \"umt5_xxl_fp8_e4m3fn_scaled.safetensors\",
      \"type\": \"wan\"
    }
  },
  \"3\": {
    \"class_type\": \"CLIPTextEncode\",
    \"inputs\": {
      \"text\": \"[PROMPT]\",
      \"clip\": [\"2\", 0]
    }
  },
  \"4\": {
    \"class_type\": \"CLIPTextEncode\",
    \"inputs\": {
      \"text\": \"[NEGATIVE]\",
      \"clip\": [\"2\", 0]
    }
  },
  \"5\": {
    \"class_type\": \"CLIPVisionLoader\",
    \"inputs\": {
      \"clip_name\": \"clip_vision_h.safetensors\"
    }
  },
  \"6\": {
    \"class_type\": \"LoadImage\",
    \"inputs\": {
      \"image\": \"[IMAGE_NAME]\"
    }
  },
  \"7\": {
    \"class_type\": \"CLIPVisionEncode\",
    \"inputs\": {
      \"crop\": \"center\",
      \"clip_vision\": [\"5\", 0],
      \"image\": [\"6\", 0]
    }
  },
  \"10\": {
    \"class_type\": \"VAELoader\",
    \"inputs\": {
      \"vae_name\": \"wan_2.1_vae.safetensors\"
    }
  },
  \"11\": {
    \"class_type\": \"WanVideoTeaCacheKJ\",
    \"inputs\": {
      \"model\": [\"1\", 0],
      \"rel_l1_thresh\": 0.3,
      \"start_percent\": 0.1,
      \"end_percent\": 1.0,
      \"cache_device\": \"offload_device\",
      \"coefficients\": \"i2v_480\"
    }
  },
  \"8\": {
    \"class_type\": \"WanImageToVideo\",
    \"inputs\": {
      \"positive\": [\"3\", 0],
      \"negative\": [\"4\", 0],
      \"vae\": [\"10\", 0],
      \"width\": 480,
      \"height\": 832,
      \"length\": 81,
      \"batch_size\": 1,
      \"clip_vision_output\": [\"7\", 0],
      \"start_image\": [\"6\", 0]
    }
  },
  \"12\": {
    \"class_type\": \"KSampler\",
    \"inputs\": {
      \"model\": [\"11\", 0],
      \"positive\": [\"8\", 0],
      \"negative\": [\"8\", 1],
      \"latent_image\": [\"8\", 2],
      \"seed\": SEED_VALUE,
      \"steps\": 30,
      \"cfg\": 1.0,
      \"sampler_name\": \"euler\",
      \"scheduler\": \"simple\",
      \"denoise\": 1.0
    }
  },
  \"13\": {
    \"class_type\": \"VAEDecode\",
    \"inputs\": {
      \"samples\": [\"12\", 0],
      \"vae\": [\"10\", 0]
    }
  },
  \"9\": {
    \"class_type\": \"VHS_VideoCombine\",
    \"inputs\": {
      \"images\": [\"13\", 0],
      \"frame_rate\": 16,
      \"loop_count\": 0,
      \"filename_prefix\": \"[OUTPUT_PREFIX]\",
      \"format\": \"video/h264-mp4\",
      \"pingpong\": False,
      \"save_output\": True
    }
  }
}

data = json.dumps({\"prompt\": workflow}).encode()
req = urllib.request.Request(\"http://localhost:8188/prompt\", data=data, headers={\"Content-Type\": \"application/json\"})
res = urllib.request.urlopen(req)
print(json.loads(res.read()))
"'
```

**⚠️ 重要: ワークフローのノード構成はComfyUIのバージョンやカスタムノードのバージョンによって変わることがある。** APIが400/500エラーを返した場合:

1. `ssh SSH_HOST "python3 -c \"import json,urllib.request; print(json.dumps(list(json.loads(urllib.request.urlopen('http://localhost:8188/object_info').read()).keys())[:30]))\""` でノード一覧を確認
2. 必要なノード名（`UnetLoaderGGUF`, `WanImageToVideo` 等）が存在するか確認
3. ノード名が違う場合はワークフローを修正して再送信

**seed値**: `SEED_VALUE` はランダムで生成する。同じシーンを複数回生成する場合はseedを変える。

```python
import random; random.randint(1, 2**32)
```

---

### Step 11: 生成完了をポーリングする

ワークフロー送信後、ComfyUI APIでキュー状況を確認する。

```bash
ssh -o StrictHostKeyChecking=no SSH_HOST 'python3 -c "
import json, urllib.request
queue = json.loads(urllib.request.urlopen(\"http://localhost:8188/queue\").read())
print(\"Running:\", len(queue.get(\"queue_running\", [])))
print(\"Pending:\", len(queue.get(\"queue_pending\", [])))
" && nvidia-smi | grep MiB'
```

- Running: 0 かつ Pending: 0 → 生成完了。Step 12 へ。
- Running: 1 以上 → 生成中。60秒待ってから再確認。
- **Wan 2.1 I2V 14B (GGUF Q5_K_M) の生成時間目安: RTX 4090で約3〜5分/本**

生成中はVRAM使用量も確認し、OOMが疑われる場合は `comfyui.log` を確認する。

最大15分待っても完了しない場合は `comfyui.log` の末尾を表示してユーザーに報告。

---

### Step 12: 生成動画をダウンロードする

```bash
# 出力ファイルを確認
ssh -o StrictHostKeyChecking=no SSH_HOST "ls -lh /workspace/ComfyUI/output/[OUTPUT_PREFIX]*"

# ダウンロード
scp -o StrictHostKeyChecking=no -P [PORT] -i ~/.ssh/id_ed25519 \
  "root@[IP]:/workspace/ComfyUI/output/[OUTPUT_PREFIX]_00001.mp4" \
  "/Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/[ファイル名].mp4"
```

**ファイル名規則:** `scene[番号]_[コンセプト名]_wan21.mp4`

例:
- `scene1_商品フォーカス_wan21.mp4`
- `scene2_使用シーン_wan21.mp4`
- `scene3_ブランド世界観_wan21.mp4`

---

### Step 13: 結果を報告する

ダウンロード完了後、以下をまとめてユーザーに報告する:

```
✅ Wan 2.1 I2V 動画生成完了

| シーン | ファイル | 解像度 | seed |
|-------|---------|--------|------|
| Scene 1 | scene1_xxx_wan21.mp4 | 480×832 | 12345 |
| Scene 2 | scene2_xxx_wan21.mp4 | 480×832 | 67890 |
| Scene 3 | scene3_xxx_wan21.mp4 | 480×832 | 11111 |

保存先: 作業中動画/
生成時間: 約X分

気に入らないシーンがあればseedを変えて再生成できます。
```

---

### 注意点

- **視聴者体験を先に設計する**: 技術制約（480p、GGUF量子化等）は後。体験の要求から逆算して制約の乗り越え方を考える。
- **動詞より状態で指定する（ただし体験の核心なら動詞も使う）**: Wan 2.1は動詞を無視しやすいか誇張しやすい。体験に不要な動きは状態で表現。体験の核心は動詞＋修飾でコントロール。
- **プロンプトはシンプルに**: Wan 2.1はKling/Runwayほどプロンプト理解力が高くない。指示は1〜2文に絞り、品質ブースト接尾辞を付ける。
- **カメラワークは1つだけ**: 複数のカメラ指示を書くと無視される。最も重要な1つだけ書く。
- **SSH接続情報は毎回確認**: RunPodはPod再起動のたびにIPとポートが変わる。Step 0 で毎回確認する。
- **ComfyUI APIのノード名は変動しうる**: カスタムノードのアップデートでノード名が変わることがある。エラー時は object_info エンドポイントで確認する。
- **コスト**: RunPod RTX 4090 = 約$0.69/時間。1本5秒の動画に3〜5分。3本生成で約$0.05〜0.10。
- **mp4出力**: VideoHelperSuite（VHS_VideoCombine）でh264 mp4を直接出力する。VHSが使えない場合はSaveAnimatedWEBPにフォールバックし、ffmpegで変換: `ffmpeg -i input.webp -c:v libx264 -pix_fmt yuv420p output.mp4`

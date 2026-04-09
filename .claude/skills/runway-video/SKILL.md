---
name: runway-video
description: 作業中動画フォルダの画像を分析してRunway（MCP経由）用のプロンプトを作成し、そのままRunwayで動画生成まで実行する。Runwayで動画作って、Runway用プロンプト、gen4_turboで生成、gen4.5で生成、動画生成して、という場面で必ず使う。
allowed-tools: Bash(ls *), Bash(curl *), Read, Write, mcp__runway__runway_generateVideo, mcp__runway__runway_getTask, mcp__runway__runway_getOrg
---

## Runway動画生成（MCP経由）

`作業中動画/` 内の画像を分析し、Runway image-to-videoに最適な英語プロンプトを生成してRunway MCPで動画生成まで実行する。

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
④ 技術指示に変換する（プロンプト文言・カメラ・照明）
```

**技術制約は「視聴者体験を諦める理由」にならない。** Runwayの制約も乗り越えるべき障壁であり、体験の設計を変える理由ではない。

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

ユーザーにこの設計を提示して確認を得てから Step 4 に進む。

---

### Step 4: 動画構成をユーザーと確認する

以下をまとめてユーザーに聞く:

1. **シーン数**: 何本のクリップを作るか（通常3本）
2. **各シーンのコンセプト**: Step 3 の感情フローをベースに提案する
3. **モデル選択**: 練習用（gen4_turbo / $0.25/本）か本番（gen4.5 / $0.60/本）か

ユーザーの回答を受けてから Step 5 に進む。

---

### Step 5: プロンプトを生成する

#### Runway Gen-4固有のプロンプト設計

**参照画像に写っているものを再説明しない**
画像が視覚情報（色・スタイル・被写体の外見）を伝える。プロンプトで同じ内容を繰り返すとモーションが減る。プロンプトは「動き」と「カメラ」と「雰囲気」のみを書く。

**英語で書く**: Runwayへの入力は英語のみ。

**縦型動画**: ratio は常に `720:1280`（9:16）、duration は `5` 秒固定。

#### プロンプトの4要素構造

RunwayはKlingと異なり動詞を直接使える。以下の4要素を順番に書く：

```
[1. 被写体の動き] [2. シーンの動き] [3. カメラの動き] [4. スタイル]
```

| 要素 | 内容 | 例 |
|------|------|----|
| **被写体の動き** | 何がどう動くか（動詞OK） | `She glances softly toward the window` |
| **シーンの動き** | 環境・背景の動き | `Dust particles float in the air` |
| **カメラの動き** | 撮影技法の専門用語 | `Slow dolly in` |
| **スタイル** | 映像の質感・雰囲気 | `Cinematic, warm tones, 4K` |

#### カメラワーク（Gen-4対応の専門用語）

- `slow dolly in` / `dolly out`（前後移動・商品に迫る）
- `tracking shot`（被写体と並走・横移動）
- `slow pan left/right`（横回転・空間を見せる）
- `tilt up` / `tilt down`（上下角度変化）
- `handheld`（自然な揺れ・リアル感）
- `static shot`（固定・静謐感）

#### 照明の書き方（光源＋効果の両方を書く）

KlingはカメラワークがメインだがRunwayは照明表現も重要。光源と効果を両方指定する：

| 光源のみ（弱い） | 光源＋効果（強い） |
|--------------|----------------|
| `sunset light` | `Golden hour sunlight casting long warm shadows` |
| `window light` | `Diffused window light from the left, soft highlights on skin` |
| `studio light` | `Studio three-point lighting, rim light separating subject from background` |
| `backlight` | `Backlighting with rim light effect, subject silhouetted against bright background` |

#### プロンプトテンプレート

**商品のみ（image-to-video）:**
```
[商品の動き or カメラ接近]. [環境の動き（煙・光・粒子など）]. [カメラワーク]. [照明（光源＋効果）]. Cinematic, 4K.
```
例:
```
Steam gently rises from the surface. Dust particles float in warm air. Slow dolly in toward the product. Soft overhead light creating subtle highlights on the surface. Cinematic, warm tones, 4K.
```

**人物メイン（image-to-video）:**
```
[人物の動き（直接的な動詞OK）]. [小道具・環境の動き]. [カメラワーク]. [照明（光源＋効果）]. Cinematic, 4K.
```
例:
```
She glances softly toward the window with a calm expression. Her hair moves gently in a breeze. Slow tracking shot from left to right. Golden hour sunlight from the right casting warm shadows. Cinematic, 4K.
```

---

### Step 6: プロンプト.mdに保存する

`/Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/プロンプト.md` に書き出す（上書き）。

**出力フォーマット:**

```markdown
# [案件名] Runwayプロンプト

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
**モデル:** gen4_turbo（練習） / gen4.5（本番）
**比率:** 720:1280（縦型9:16）
**尺:** 5秒

**プロンプト（英語）**
```
[プロンプト本文]
```

**視聴者体験:** [このシーンで何を感じさせるか]
**動きの指示:** [日本語で1行の動き説明]

---

## Scene 2 — ...

（以下同様）
```

保存後、プロンプト内容をユーザーに提示し、**ここで必ず止まる**。

「プロンプトを保存しました。修正があればお知らせください。問題なければ「はい」と言ってください。」と伝えて待機する。

---

### Step 7: 生成指示を受けてから進む

ユーザーから「生成して」「OK」「このまま進めて」などの明示的な指示を受けてから Step 8 に進む。

プロンプトの修正を求められた場合は `プロンプト.md` を編集して再度ユーザーに提示し、再度待機する。

---

### Step 8: Runway MCPで動画生成を実行する

`mcp__runway__runway_generateVideo` でシーンごとに生成する。

**モデルID:**
- 練習用: `gen4_turbo`
- 本番: `gen4.5`

**固定パラメータ:**
- ratio: `720:1280`
- duration: `5`
- 参照画像: **必ず公開URLで渡す**（後述の手順を参照）

**⚠️ 重要: 参照画像はローカルパスを渡してはいけない**

RunwayのサーバーはMacのローカルファイルにアクセスできない。ローカルパスを渡すと `400 Could not process image` エラーになる。必ずfal.aiで先にアップロードして公開URLを取得してから渡すこと。

```
# 手順: fal.aiでアップロード → 公開URLを取得 → RunwayにURLを渡す
mcp__fal-ai__upload_file({ file_path: "/Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/sean1.png" })
# → 返ってきたURLをRunwayの imageUri に使う
```

複数シーンは並列実行する（同時に投げる）。

生成後は `mcp__runway__runway_getTask` でステータスを確認し、完了を待つ。

---

### Step 8: 生成動画を作業中動画フォルダに保存する

生成されたURLをBash（curl）でダウンロードする。

ファイル名規則: `scene[番号]_[コンセプト名]_runway_[モデル略称].mp4`

例:
- `scene1_商品フォーカス_runway_gen4t.mp4`（gen4_turbo）
- `scene1_商品フォーカス_runway_gen4.mp4`（gen4.5）

```bash
curl -sL "[生成URL]" -o "/Users/keeee/Desktop/Dev/OssMovieAIz/作業中動画/[ファイル名].mp4"
```

保存完了後、生成した動画のファイル名・モデル・推定コストをまとめてユーザーに報告する。

---

### コスト早見表

| モデル | 料金/秒 | 5秒/本 |
|--------|--------|--------|
| gen4_turbo | $0.05 | $0.25 |
| gen4.5 | $0.12 | $0.60 |

---

### 注意点

- **視聴者体験を先に設計する**: 技術制約は後。体験の要求から逆算して制約の乗り越え方を考える。
- **画像の内容を再説明しない**: 参照画像が視覚情報を担う。プロンプトで繰り返すとモーションが減る。
- **RunwayはKlingと違い動詞を直接使える**: `glances`, `walks`, `rises` など自然な動詞でOK。体験の核心を表す動詞は積極的に使い、不要な動きは状態で表現する。
- **照明は光源と効果の両方を書く**: `golden hour sunlight` より `golden hour sunlight casting warm shadows` の方が精度が上がる。
- **gen4_turboは画像入力必須**: テキストのみでの生成はgen4.5を使う。
- **コスト確認**: 生成前にユーザーにモデルとコストを確認する。
- **Klingとの使い分け**: 光・大気感・シネマティック感を重視するならRunway。参照画像に忠実に動かしたいならKling。

---
name: flux-face-prompt
description: >
  画像から人物の顔を極めて詳細に分析し、Flux画像生成モデル向けの英語プロンプトを生成するスキル。
  ユーザーが画像を渡して「顔のプロンプトを作って」「Flux用のプロンプト」「この人の顔を描写して」
  「顔の特徴をプロンプトにして」などと言ったときに必ずこのスキルを使うこと。
  画像に人物が写っている場合で、顔の描写・プロンプト生成・Flux/SD/Midjourney等の
  画像生成AI向けプロンプトに関する依頼があれば、明示的に言及されなくてもこのスキルをトリガーすること。
---

<!-- NOTE: 2026-04 方針変更により、通常の動画制作フロー（Step 6）ではこのスキルを使用しない。
     顔の一貫性はLoRAで担保する方針に移行したため、プロンプトに顔の詳細は記述しない。
     PuLIDも商用利用不可のため使用しない。
     このスキルは単体で顔分析プロンプトが必要な場合のために残している。 -->

# Flux Face Prompt Generator

画像に写っている人物の顔を網羅的に観察し、Flux向けの超詳細な英語プロンプトを生成するスキル。

## ワークフロー

1. ユーザーから画像を受け取る
2. 下記の「観察チェックリスト」に沿って顔のすべての要素を観察する
3. 観察結果をFlux向けの構造化された英語プロンプトとして出力する

## 観察チェックリスト

画像を受け取ったら、以下の **全カテゴリ** を一つずつ確認し、該当する特徴を記述すること。
特徴が確認できない場合はスキップしてよいが、確認できるものは漏らさず記述する。

### 1. 骨格・輪郭 (Bone Structure & Face Shape)
- 顔の輪郭（oval / round / square / heart / diamond / oblong）
- 顎の形・角度・幅（jawline shape, angle, width）
- エラの張り具合（jaw angle prominence）
- こめかみの凹凸（temple area）
- 顎先の形状（chin shape: pointed / rounded / square / cleft）
- 頬骨の高さ・出方（cheekbone height and prominence）
- 眉骨の突出度（brow bone ridge）
- 顔全体の左右非対称性（facial asymmetry）

### 2. 額・おでこ (Forehead)
- 額の広さ・高さ（forehead width and height）
- 額の丸み・傾斜（forehead curvature / slope）
- 生え際の形（hairline shape: rounded / M-shaped / widow's peak）
- 額のシワ（forehead wrinkles / lines）
- 額の質感（texture, sheen）

### 3. 眉 (Eyebrows)
- 眉の形（straight / arched / curved / angled）
- 眉の太さ・濃さ（thickness, density）
- 眉の長さ（length relative to eye）
- 眉頭・眉山・眉尻の位置と角度
- 眉と目の距離（brow-to-eye distance）
- 手入れの状態（groomed / natural / bushy）

### 4. 目の周辺 (Eye Area)
- まぶたの種類（monolid / double lid / hooded / deep-set）
- まぶたの厚み（lid thickness）
- 二重幅（double eyelid crease width）
- 蒙古ひだの有無（epicanthic fold）
- 目の形・傾き（eye shape: almond / round / upturned / downturned）
- 目の大きさ（eye size relative to face）
- 目の間隔（interocular distance）
- 涙袋の大きさ（tear trough / aegyo-sal prominence）
- 目の下のクマ・たるみ（under-eye darkness / puffiness）
- 目尻のシワ（crow's feet）
- 眼窩の彫りの深さ（orbital depth）
- まつ毛の長さ・密度・カール（lash length, density, curl）
- 目の色（iris color）
- 白目の状態（sclera clarity）

### 5. 鼻 (Nose)
- 鼻根の高さ・幅（nose bridge height and width）
- 鼻筋の通り具合（dorsum straightness / curvature）
- 鼻先の形（nose tip shape: rounded / pointed / bulbous / upturned）
- 小鼻の張り具合（alar width / flare）
- 鼻翼の形（nostril shape）
- 鼻の全体サイズ（overall nose size relative to face）
- 鼻の角度（nasal angle from profile if visible）

### 6. 人中 (Philtrum)
- 人中の長さ（philtrum length）
- 人中の深さ・溝の明確さ（philtrum depth and definition）
- 人中の幅（philtrum width）
- 人中の稜線（philtral ridges）

### 7. 口・唇周辺 (Mouth & Lip Area)
- 唇の厚さ（上唇・下唇それぞれ）（upper/lower lip thickness）
- 唇の幅（lip width）
- キューピッドボウの形（cupid's bow definition）
- 唇の色・質感（lip color, texture: matte / glossy / chapped）
- 口角の位置・角度（mouth corner position: upturned / neutral / downturned）
- 口の開閉状態（open / closed / slightly parted）
- ほうれい線の有無・深さ（nasolabial fold depth）
- マリオネットラインの有無（marionette lines）
- 顎の梅干しジワ（chin dimpling / mentalis strain）

### 8. 頬 (Cheeks)
- 頬のふっくら感 or こけ具合（cheek fullness / hollowness）
- 頬の脂肪のつき方（buccal fat prominence）
- えくぼの有無・位置（dimple presence and location）
- ゴルゴライン（mid-cheek groove / malar groove）
- 頬の赤み・血色（cheek flush / blush）

### 9. 耳 (Ears)
- 耳の大きさ（ear size）
- 耳の角度・立ち具合（ear protrusion / angle）
- 耳たぶの形（earlobe shape: attached / detached）
- ピアス穴の有無（piercing presence）
- 見え具合（visibility — 髪で隠れている場合は記述不要）

### 10. 肌の質感・状態 (Skin Quality & Texture)
- 肌の色・トーン（skin tone: fair / medium / olive / dark）
- アンダートーン（undertone: warm / cool / neutral）
- 肌のキメ（skin texture: smooth / rough / textured）
- 毛穴の目立ち具合（pore visibility）
- ツヤ・テカリ・マット感（skin finish: dewy / matte / oily）
- 透明感（skin translucency / luminosity）
- そばかす（freckles）
- シミ（age spots / hyperpigmentation）
- ほくろの位置と大きさ（mole placement and size）
- ニキビ・ニキビ跡（acne / acne scarring）
- 赤み（redness / rosacea）
- 色ムラ（skin tone unevenness）
- 産毛（peach fuzz / vellus hair）
- 傷跡（scars）

### 11. シワ・ライン (Wrinkles & Lines)
- 額の横ジワ（forehead horizontal lines）
- 眉間の縦ジワ（glabellar lines / frown lines）
- 目尻のシワ（crow's feet）
- ほうれい線（nasolabial folds）
- マリオネットライン（marionette lines）
- ゴルゴライン（malar grooves）
- 口周りの縦ジワ（perioral lines / smoker's lines）
- 首のシワ（neck lines / tech neck）

### 12. ヒゲ・体毛 (Facial Hair)
- 無精ヒゲ / スタブル（stubble）
- 口ひげの形状・濃さ（mustache style and density）
- あごひげの形状（goatee / beard shape）
- もみあげの長さ・形（sideburn length and shape）
- 頬のヒゲの生え方（cheek hair growth pattern）
- 剃り跡・青ヒゲ（shaving shadow / five o'clock shadow）
- 眉間の毛（unibrow tendency）

### 13. 血色・色味 (Complexion & Color)
- 頬の紅潮（cheek flush）
- 鼻先の赤み（nasal tip redness）
- 唇周りの色素沈着（perioral pigmentation）
- 目の周りのくすみ（periorbital darkening）
- 日焼けの境目（tan lines）
- 全体のアンダートーン（overall undertone）

### 14. 顔のプロポーション (Facial Proportions)
- 三庭（額〜眉、眉〜鼻下、鼻下〜顎）のバランス
- 五眼（顔幅と目の間隔の比率）
- 顔の縦横比（face length-to-width ratio）

### 15. 表情 (Expression)
- 現在の表情（neutral / smiling / serious / surprised 等）
- 表情筋の緊張状態（muscle tension）
- 視線の方向と強さ（gaze direction and intensity）
- 口の状態（lips parted / closed / smiling）

## 出力フォーマット

観察結果を以下の構造で **英語の自然文プロンプト** として出力する。
箇条書きではなく、Fluxが理解しやすい流れるような記述文にすること。

```
[人物の基本属性: 性別、年齢層、民族的特徴]

[骨格・輪郭の描写]

[額・おでこの描写]

[眉の描写]

[目の周辺の描写]

[鼻の描写]

[人中の描写]

[口・唇周辺の描写]

[頬の描写]

[耳の描写（見えている場合）]

[肌の質感・状態の描写]

[シワ・ラインの描写（該当する場合）]

[ヒゲ・体毛の描写（該当する場合）]

[血色・色味の描写]

[顔のプロポーションの描写]

[表情の描写]
```

## 重要なルール

1. **英語で出力する**: Fluxは英語プロンプトで最高の結果を出すため、プロンプト本文は必ず英語で書く
2. **具体的に書く**: 「beautiful」「pretty」などの曖昧な形容詞は避け、具体的な形状・サイズ・位置関係で描写する
3. **比較表現を活用する**: 「slightly larger than average」「narrower than the mouth width」など相対的な表現を使う
4. **観察できないものは書かない**: 画像から確認できない特徴は推測で書かず、省略する
5. **Flux向けに最適化する**: 写真的リアリズムを重視し、アーティスティックな比喩表現は避ける
6. **顔以外は含めない**: 服装、髪型、背景、ポーズは別途指示がない限り含めない。あくまで顔の描写に集中する
7. **全カテゴリを網羅する**: チェックリストの全項目を確認し、該当するものはすべて記述に含める

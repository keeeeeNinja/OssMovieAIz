#!/bin/bash
# プロジェクト初期化スクリプト
# 次の動画制作に入る前に実行し、前回の動画のコード・素材をリセットする

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== プロジェクト初期化 ==="
echo "Project: $PROJECT_DIR"
echo ""

# 1. AdVideo.tsx を空テンプレートに戻す
echo "[1/3] AdVideo.tsx をテンプレートにリセット..."
cat <<'EOF' > "$PROJECT_DIR/src/compositions/AdVideo.tsx"
import React from "react";
import { AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

// ===== デフォルトアニメーション（タイプライター式blurフェードイン） =====
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

// ===== 1行テロップ自動フォントサイズ =====
const calcFontSize = (text: string, baseChars: number, baseSize: number) => {
  if (text.length <= baseChars) return baseSize;
  return Math.max(64, Math.round(baseSize * (baseChars / text.length)));
};

// ===== トランジション（白フラッシュ） =====
const FLASH_FRAMES = 8;

// ===== クリップ定義（bs分析後に上書きされる） =====
const clips: {
  file: string;
  durationInFrames: number;
  render: (frame: number) => React.ReactNode;
}[] = [
  // Step 3 で bs分析結果のテロップがここに入る
];

// ===== Telopコンポーネント =====
const Telop: React.FC<(typeof clips)[number]> = (clip) => {
  const frame = useCurrentFrame();
  if (clip.render) return clip.render(frame);
  return null;
};

// ===== 白フラッシュトランジション =====
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
      <Audio src={staticFile("narration.wav")} volume={0.4} />
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
EOF
echo "  -> done"

# 2. public/ から前回の動画素材を削除（bgm/narrationも含む）
echo "[2/3] public/ の動画・音声素材をクリア..."
rm -f "$PROJECT_DIR"/public/scene_*.mp4
rm -f "$PROJECT_DIR"/public/bgm.mp3
rm -f "$PROJECT_DIR"/public/narration.wav
echo "  -> done"

# 3. 作業中動画/ をクリア（theme1〜5フォルダは再作成）
echo "[3/3] 作業中動画/ をクリア..."
rm -rf "$PROJECT_DIR/作業中動画/"
mkdir -p "$PROJECT_DIR/作業中動画/theme1"
mkdir -p "$PROJECT_DIR/作業中動画/theme2"
mkdir -p "$PROJECT_DIR/作業中動画/theme3"
mkdir -p "$PROJECT_DIR/作業中動画/theme4"
mkdir -p "$PROJECT_DIR/作業中動画/theme5"
echo "  -> done"

echo ""
echo "=== 初期化完了 ==="
echo "AdVideo.tsx: テンプレート状態"
echo "public/: 素材クリア済み"
echo "作業中動画/: theme1〜5フォルダ作成済み"
echo ""
echo "次の動画制作を始めてください。"

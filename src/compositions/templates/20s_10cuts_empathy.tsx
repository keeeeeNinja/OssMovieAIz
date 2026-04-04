/**
 * テンプレート: 20s_10cuts_empathy
 * 共感系ショート動画（20秒・10カット）
 *
 * 構成:
 *   フック(2s) → 悩み×3(1.5s×3) → 悩みピーク(2s) → 転換(2s) → 解決策(2s) → 効果(2s) → クライマックス(3s) → CTA(2s)
 *
 * 使い方:
 *   1. clips配列のfile・main・subを差し替える
 *   2. public/にクリップ・narration.wav・bgm.mp3を配置
 *   3. npm run render
 */

import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

// ===== 基準フォントサイズ（バズ動画の7文字が画面縦いっぱいに収まるサイズ） =====
const BASE_FONT_SIZE = 180;
const BASE_CHAR_COUNT = 7;
const SCREEN_HEIGHT = 1920;
const MAX_TEXT_HEIGHT = SCREEN_HEIGHT * 0.85; // テキストが使える縦幅の上限

// 文字数に応じてフォントサイズを自動調整（必ず1行に収める）
const calcFontSize = (text: string): number => {
  const needed = text.length * BASE_FONT_SIZE * 1.35; // letterSpacing+lineHeight考慮
  if (needed <= MAX_TEXT_HEIGHT) return BASE_FONT_SIZE;
  return Math.floor(MAX_TEXT_HEIGHT / (text.length * 1.35));
};

// ===== テロップスタイル生成 =====
const makeTelopStyle = (fontSize: number): React.CSSProperties => ({
  fontSize,
  fontWeight: 900,
  fontFamily: "Hiragino Maru Gothic ProN, Rounded Mplus 1c, sans-serif",
  color: "#FFFFFF",
  WebkitTextStroke: `${Math.max(3, Math.round(fontSize / 30))}px #000000`,
  paintOrder: "stroke fill",
  writingMode: "vertical-rl" as const,
  lineHeight: 1.3,
  letterSpacing: "0.05em",
});

// 上部小テキスト用（横書き）
const subTextStyle: React.CSSProperties = {
  fontSize: 40,
  fontWeight: 700,
  fontFamily: "Hiragino Maru Gothic ProN, Rounded Mplus 1c, sans-serif",
  color: "#FFFFFF",
  WebkitTextStroke: "2px #000000",
  paintOrder: "stroke fill",
};

// ===== デフォルトアニメーション（タイプライター式blurフェードイン） =====
const animC = (frame: number, text: string, startFrame = 3) => {
  const CHARS_DURATION = 8;
  const FADE_FRAMES = 10;
  const charsPerFrame = text.length / CHARS_DURATION;
  return text.split("").map((char, i) => {
    const charAppearFrame = startFrame + Math.floor(i / charsPerFrame);
    const age = frame - charAppearFrame;
    if (age < 0) return null;
    const t = Math.min(1, age / FADE_FRAMES);
    return (
      <span key={i} style={{ opacity: t, filter: `blur(${(1 - t) * 20}px)` }}>{char}</span>
    );
  });
};

// ===== クリップ定義（★ ここを差し替える） =====
const clips = [
  { file: "scene01_hook.mp4",      durationInFrames: 60,  main: "フックテキスト",       sub: null },
  { file: "scene02_problem1.mp4",  durationInFrames: 45,  main: "悩み①テキスト",        sub: null },
  { file: "scene03_problem2.mp4",  durationInFrames: 45,  main: "悩み②テキスト",        sub: null },
  { file: "scene04_problem3.mp4",  durationInFrames: 45,  main: "悩み③テキスト",        sub: null },
  { file: "scene05_peak.mp4",      durationInFrames: 60,  main: "悩みピークテキスト",    sub: null },
  { file: "scene06_turn.mp4",      durationInFrames: 60,  main: "転換テキスト",          sub: null },
  { file: "scene07_solution.mp4",  durationInFrames: 60,  main: "解決策テキスト",        sub: "サブテキスト" },
  { file: "scene08_effect.mp4",    durationInFrames: 60,  main: "効果テキスト",          sub: null },
  { file: "scene09_climax.mp4",    durationInFrames: 90,  main: "クライマックステキスト", sub: null },
  { file: "scene10_cta.mp4",       durationInFrames: 60,  main: "CTAテキスト",           sub: null },
];

// ===== テロップコンポーネント =====
const TelopText: React.FC<{ clip: (typeof clips)[number] }> = ({ clip }) => {
  const frame = useCurrentFrame();
  const fontSize = calcFontSize(clip.main);
  const style = makeTelopStyle(fontSize);
  return (
    <>
      {clip.sub && (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-start", paddingTop: 160, paddingLeft: 48 }}>
          <div style={subTextStyle}>
            {animC(frame, clip.sub, 1)}
          </div>
        </AbsoluteFill>
      )}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={style}>
          {animC(frame, clip.main, 3)}
        </div>
      </AbsoluteFill>
    </>
  );
};

// ===== メインコンポーネント =====
export const AdVideo: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Audio src={staticFile("narration.wav")} volume={0.4} />
      <Audio src={staticFile("bgm.mp3")} volume={0.15} />
      {clips.map((clip) => {
        const start = from;
        from += clip.durationInFrames;
        return (
          <Sequence key={clip.file} from={start} durationInFrames={clip.durationInFrames}>
            <AbsoluteFill>
              <OffthreadVideo
                src={staticFile(clip.file)}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
              <TelopText clip={clip} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

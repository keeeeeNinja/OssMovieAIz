import React from "react";
import { AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

export const animC = (frame: number, text: string, startFrame = 3) => {
  const CHARS_DURATION = 10;
  const FADE_FRAMES = 12;
  const charsPerFrame = text.length / CHARS_DURATION;
  return text.split("").map((char, i) => {
    if (char === "\n") return <br key={i} />;
    const charAppearFrame = startFrame + Math.floor(i / charsPerFrame);
    const age = frame - charAppearFrame;
    if (age < 0) return null;
    const t = Math.min(1, age / FADE_FRAMES);
    return (
      <span key={i} style={{ opacity: t, filter: `blur(${(1 - t) * 18}px)` }}>{char}</span>
    );
  });
};

export const telopBase = (fontSize: number, borderWidth: number): React.CSSProperties => ({
  color: "#FF0000",
  fontFamily: '"Noto Sans JP", "Hiragino Sans", sans-serif',
  fontWeight: 900,
  fontSize,
  lineHeight: 1.2,
  textAlign: "center",
  WebkitTextStroke: `${borderWidth}px #FFFFFF`,
  paintOrder: "stroke fill",
  whiteSpace: "pre-line",
});

export const wrapperBase = (y: number): React.CSSProperties => ({
  position: "absolute",
  top: `${y * 100}%`,
  left: 0,
  right: 0,
  transform: "translateY(-50%)",
  display: "flex",
  justifyContent: "center",
});

export type Clip = {
  // Step 5（bsベースライン実装時）はクリップ未生成なので空文字にする。
  // その場合は OffthreadVideo をレンダーせず黒背景＋テロップだけ表示する。
  file: string;
  durationInFrames: number;
  render: (frame: number) => React.ReactNode;
};

const FLASH_FRAMES = 6;

const Telop: React.FC<Clip> = (clip) => {
  const frame = useCurrentFrame();
  return <>{clip.render(frame)}</>;
};

const WhiteFlash: React.FC<{ clips: Clip[] }> = ({ clips }) => {
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
    return Math.max(o, interpolate(dist, [0, FLASH_FRAMES], [0.9, 0], { extrapolateRight: "clamp" }));
  }, 0);
  if (opacity === 0) return null;
  return <AbsoluteFill style={{ backgroundColor: `rgba(255,255,255,${opacity})`, zIndex: 10 }} />;
};

export type AdVideoOptions = {
  clips: Clip[];
  bgm?: string;
  narration?: string;
  bgmVolume?: number;
  narrationVolume?: number;
};

export const AdVideoBase: React.FC<AdVideoOptions> = ({ clips, bgm, narration, bgmVolume = 0.35, narrationVolume = 0.4 }) => {
  let from = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {bgm && <Audio src={staticFile(bgm)} volume={bgmVolume} />}
      {narration && <Audio src={staticFile(narration)} volume={narrationVolume} />}
      {clips.map((clip, idx) => {
        const start = from;
        from += clip.durationInFrames;
        return (
          <Sequence key={`${clip.file || "placeholder"}-${idx}`} from={start} durationInFrames={clip.durationInFrames}>
            <AbsoluteFill>
              {clip.file && (
                <OffthreadVideo
                  src={staticFile(clip.file)}
                  style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center center" }}
                />
              )}
              <Telop {...clip} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <WhiteFlash clips={clips} />
    </AbsoluteFill>
  );
};

import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";

// ===== デフォルトアニメーション（全シーン共通） =====
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

// ===== クリップ定義 =====
const clips = [
  {
    file: "scene1.mp4",
    durationInFrames: 92,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-start",
        alignItems: "flex-start",
        paddingTop: 160,
        paddingLeft: 48,
      }}>
        <div style={{
          fontSize: 96,
          fontWeight: 800,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.15em",
          lineHeight: 1.25,
          color: "#2A2A2A",
          whiteSpace: "pre-line" as const,
        }}>
          {animC(frame, "その化粧水、\n肌に届いてる？")}
        </div>
      </AbsoluteFill>
    ),
  },
  {
    file: "scene2.mp4",
    durationInFrames: 92,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 240,
      }}>
        <div style={{
          fontSize: 80,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.25em",
          lineHeight: 1.5,
          color: "#1A1A1A",
          textAlign: "center" as const,
        }}>
          {animC(frame, "浸透力が、まるで違う")}
        </div>
      </AbsoluteFill>
    ),
  },
  {
    file: "scene3.mp4",
    durationInFrames: 92,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "center",
        alignItems: "flex-end",
        paddingRight: 64,
      }}>
        <div style={{
          writingMode: "vertical-rl" as const,
          fontSize: 72,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.3em",
          lineHeight: 1,
          color: "#2A2A2A",
          textShadow: "0 1px 16px rgba(255,255,255,0.6)",
        }}>
          {animC(frame, "つけた瞬間、もちもち肌へ")}
        </div>
      </AbsoluteFill>
    ),
  },
  {
    file: "scene4.mp4",
    durationInFrames: 92,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        paddingBottom: 140,
        paddingLeft: 56,
      }}>
        <div style={{
          fontSize: 84,
          fontWeight: 600,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.02em",
          lineHeight: 1.3,
          color: "#2A2A2A",
          textShadow: "0 2px 16px rgba(255,255,255,0.5)",
        }}>
          {animC(frame, "自信が持てる素肌に")}
        </div>
      </AbsoluteFill>
    ),
  },
  {
    file: "scene5.mp4",
    durationInFrames: 92,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-start",
        alignItems: "flex-end",
        paddingTop: 180,
        paddingRight: 56,
      }}>
        <div style={{
          fontSize: 72,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.1em",
          lineHeight: 1.6,
          color: "#3D3D3D",
        }}>
          {animC(frame, "NMD 詳しくはこちら")}
        </div>
      </AbsoluteFill>
    ),
  },
];

// ===== Telopコンポーネント =====
const Telop: React.FC<(typeof clips)[number]> = (clip) => {
  const frame = useCurrentFrame();
  if (clip.render) return clip.render(frame);
  return null;
};

// ===== トランジション（白フラッシュ）=====
const FLASH_FRAMES = 8;
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
      <Audio src={staticFile("bgm.mp3")} volume={0.15} />
      <Audio src={staticFile("narration.wav")} volume={0.5} />
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

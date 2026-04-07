import React from "react";
import { AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

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

// ===== 1行テロップ自動フォントサイズ =====
const calcFontSize = (text: string, baseChars: number, baseSize: number) => {
  if (text.length <= baseChars) return baseSize;
  return Math.max(64, Math.round(baseSize * (baseChars / text.length)));
};

// ===== トランジション（白フラッシュ） =====
const FLASH_FRAMES = 4;

// ===== クリップ定義 =====
const clips = [
  // C01: Hook（1.0s = 30f）— 赤太字ゴシック、画面下部
  {
    file: "scene_C01_wan21.mp4",
    durationInFrames: 30,
    render: (frame: number) => {
      const text = "これは衝撃！";
      const fontSize = calcFontSize(text, 8, 154);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 320 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FF2020",
            WebkitTextStroke: "4px #000000",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C02: Bridge（1.0s = 30f）— 黄色丸ゴシック、青シャドウ
  {
    file: "scene_C02_wan21.mp4",
    durationInFrames: 30,
    render: (frame: number) => {
      const text = "SNSでバズってる";
      const fontSize = calcFontSize(text, 8, 125);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 320 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Maru Gothic ProN, Rounded Mplus 1c, sans-serif",
            color: "#FFE500",
            WebkitTextStroke: "3px #000000",
            paintOrder: "stroke fill",
            textShadow: "3px 3px 6px rgba(0,80,200,0.8)",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C03: Main前半（1.5s = 45f）— 黄文字+黒縁
  {
    file: "scene_C03_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "このまつ毛美容液が";
      const fontSize = calcFontSize(text, 10, 106);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFE500",
            WebkitTextStroke: "3px #000000",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C04: Main前半（1.0s = 30f）— 黄文字+黒縁
  {
    file: "scene_C04_wan21.mp4",
    durationInFrames: 30,
    render: (frame: number) => {
      const text = "想像以上やった";
      const fontSize = calcFontSize(text, 8, 125);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFE500",
            WebkitTextStroke: "3px #000000",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C05: Main前半（1.5s = 45f）— 黄文字+白縁、縦書き
  {
    file: "scene_C05_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "実はこれ30日で効果が出る";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end", paddingTop: 180, paddingRight: 60 }}>
          <div style={{
            fontSize: 96, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFE500",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            writingMode: "vertical-rl",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C06: Bridge（2.0s = 60f）— ピンク文字+ピンクシャドウ、縦書き
  {
    file: "scene_C06_wan21.mp4",
    durationInFrames: 60,
    render: (frame: number) => {
      const text = "まつ毛が短くて悩んでる人は";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-end", paddingBottom: 200, paddingRight: 60 }}>
          <div style={{
            fontSize: 92, fontWeight: 900,
            fontFamily: "Hiragino Maru Gothic ProN, Rounded Mplus 1c, sans-serif",
            color: "#FF69B4",
            WebkitTextStroke: "3px #000000",
            paintOrder: "stroke fill",
            textShadow: "2px 2px 6px rgba(255,105,180,0.5)",
            writingMode: "vertical-rl",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C07: Main後半（1.5s = 45f）— 黒文字ゴシック+白縁、画面上部
  {
    file: "scene_C07_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "洗顔後の清潔な肌に";
      const fontSize = calcFontSize(text, 10, 106);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C08: Main後半（1.5s = 45f）
  {
    file: "scene_C08_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "美容液をひと塗り";
      const fontSize = calcFontSize(text, 10, 106);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C09: Main後半（2.0s = 60f）
  {
    file: "scene_C09_wan21.mp4",
    durationInFrames: 60,
    render: (frame: number) => {
      const text = "たっぷり";
      const fontSize = calcFontSize(text, 6, 154);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C10: Main後半（2.0s = 60f）
  {
    file: "scene_C10_wan21.mp4",
    durationInFrames: 60,
    render: (frame: number) => {
      const text = "まつ毛の根元に";
      const fontSize = calcFontSize(text, 10, 106);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C11: Main後半（2.0s = 60f）— 縦書き
  {
    file: "scene_C11_wan21.mp4",
    durationInFrames: 60,
    render: (frame: number) => {
      const text = "気になるところに塗っていく";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end", paddingTop: 180, paddingRight: 60 }}>
          <div style={{
            fontSize: 92, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            writingMode: "vertical-rl",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C12: Main後半（2.0s = 60f）
  {
    file: "scene_C12_wan21.mp4",
    durationInFrames: 60,
    render: (frame: number) => {
      const text = "優しくなじませて";
      const fontSize = calcFontSize(text, 10, 106);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C13: Main後半（1.5s = 45f）— 縦書き
  {
    file: "scene_C13_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "毎日続けるんがポイント";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-end", paddingTop: 180, paddingRight: 60 }}>
          <div style={{
            fontSize: 96, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            writingMode: "vertical-rl",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C14: Main後半（1.5s = 45f）
  {
    file: "scene_C14_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "30日続けたら";
      const fontSize = calcFontSize(text, 8, 125);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 280 }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            WebkitTextStroke: "3px #FFFFFF",
            paintOrder: "stroke fill",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C15: CTA（3.5s = 105f）— 黄文字丸ゴシック+赤シャドウ、画面中央
  {
    file: "scene_C15_wan21.mp4",
    durationInFrames: 105,
    render: (frame: number) => {
      const text = "この仕上がり！";
      const fontSize = calcFontSize(text, 8, 134);
      return (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
          <div style={{
            fontSize, fontWeight: 900,
            fontFamily: "Hiragino Maru Gothic ProN, Rounded Mplus 1c, sans-serif",
            color: "#FFE500",
            WebkitTextStroke: "4px #000000",
            paintOrder: "stroke fill",
            textShadow: "3px 3px 8px rgba(200,0,0,0.7)",
            letterSpacing: "0.05em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
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
    return Math.max(o, interpolate(dist, [0, FLASH_FRAMES], [0.6, 0], { extrapolateRight: "clamp" }));
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
      <Sequence from={30}>
        <Audio src={staticFile("narration.wav")} volume={0.4} />
      </Sequence>
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
              <Telop {...clip} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <WhiteFlash />
    </AbsoluteFill>
  );
};

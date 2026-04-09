import React from "react";
import { AbsoluteFill, Audio, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";

// ===== デフォルトアニメーション（タイプライター式blurフェードイン） =====
const animC = (frame: number, text: string, startFrame = 3) => {
  const CHARS_DURATION = 8;
  const FADE_FRAMES = 12;
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
const FLASH_FRAMES = 6;

// ===== クリップ定義（テーマ②: 昔の私に教えたいこと） =====
const clips = [
  // C01: フック（2.2s = 66f）— P3 上部ヘッドライン
  {
    file: "scene_T2_C01_wan21.mp4",
    durationInFrames: 66,
    render: (frame: number) => {
      const text = "昔の私に教えたいこと";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 200 }}>
          <div style={{
            fontSize: 84,
            fontWeight: 900,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFFFFF",
            textShadow: "0 3px 24px rgba(0,0,0,0.6)",
            letterSpacing: "0.02em",
            whiteSpace: "nowrap" as const,
          }}>
            {animC(frame, text, 3)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C02: 導入（1.2s = 36f）— P8 下部帯
  {
    file: "scene_T2_C02_wan21.mp4",
    durationInFrames: 36,
    render: (frame: number) => {
      const text = "あの頃の自分へ";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "stretch" }}>
          <div style={{
            backgroundColor: "rgba(0,0,0,0.45)",
            paddingTop: 20,
            paddingBottom: 28,
            textAlign: "center" as const,
          }}>
            <div style={{
              fontSize: 72,
              fontWeight: 500,
              fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
              color: "#FFFFFF",
              letterSpacing: "0.06em",
            }}>
              {animC(frame, text, 3)}
            </div>
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C03: 教訓①（3.5s = 105f）— P1 下部左寄せ
  {
    file: "scene_T2_C03_wan21.mp4",
    durationInFrames: 105,
    render: (frame: number) => {
      const text = "人の目を気にしないで";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-start", paddingBottom: 140, paddingLeft: 56 }}>
          <div style={{
            fontSize: 84,
            fontWeight: 800,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFFFFF",
            textShadow: "0 2px 16px rgba(0,0,0,0.5)",
            letterSpacing: "0.02em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C04: 教訓②（2.8s = 84f）— P3 上部中央（白文字 — 暗い映像）
  {
    file: "scene_T2_C04_wan21.mp4",
    durationInFrames: 84,
    render: (frame: number) => {
      const text = "ひとりの夜も無駄じゃない";
      const fontSize = calcFontSize(text, 10, 80);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 180 }}>
          <div style={{
            fontSize,
            fontWeight: 700,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFFFFF",
            textShadow: "0 2px 16px rgba(0,0,0,0.5)",
            letterSpacing: "0.02em",
            whiteSpace: "nowrap" as const,
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C05: 教訓③（1.0s = 30f）— P1 下部左寄せ
  {
    file: "scene_T2_C05_wan21.mp4",
    durationInFrames: 30,
    render: (frame: number) => {
      const text = "自分を好きになって";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-start", paddingBottom: 140, paddingLeft: 56 }}>
          <div style={{
            fontSize: 84,
            fontWeight: 800,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFFFFF",
            textShadow: "0 2px 16px rgba(0,0,0,0.5)",
            letterSpacing: "0.02em",
          }}>
            {animC(frame, text, 3)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C06: 転換（1.3s = 39f）— P2 中央明朝（白文字 — 暗い映像）
  {
    file: "scene_T2_C06_wan21.mp4",
    durationInFrames: 39,
    render: (frame: number) => {
      const text = "でも 今ならわかる";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 160 }}>
          <div style={{
            fontSize: 76,
            fontWeight: 300,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            color: "#FFFFFF",
            textShadow: "0 2px 20px rgba(0,0,0,0.5)",
            letterSpacing: "0.2em",
            whiteSpace: "nowrap" as const,
          }}>
            {animC(frame, text, 3)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C07: 今の自分①（2.6s = 78f）— P1 下部左寄せ（暗色 — 明るい映像）
  {
    file: "scene_T2_C07_wan21.mp4",
    durationInFrames: 78,
    render: (frame: number) => {
      const text = "好きなことを見つけた";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-start", paddingBottom: 140, paddingLeft: 56 }}>
          <div style={{
            fontSize: 84,
            fontWeight: 700,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#1A1A1A",
            letterSpacing: "0.02em",
          }}>
            {animC(frame, text)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C08: 今の自分②（1.5s = 45f）— P8 下部帯
  {
    file: "scene_T2_C08_wan21.mp4",
    durationInFrames: 45,
    render: (frame: number) => {
      const text = "小さな幸せに気づけた";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "stretch" }}>
          <div style={{
            backgroundColor: "rgba(0,0,0,0.45)",
            paddingTop: 20,
            paddingBottom: 28,
            textAlign: "center" as const,
          }}>
            <div style={{
              fontSize: 72,
              fontWeight: 500,
              fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
              color: "#FFFFFF",
              letterSpacing: "0.06em",
            }}>
              {animC(frame, text, 3)}
            </div>
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C09: 今の自分③（1.0s = 30f）— P5 左上ミニマル（暗色 — 明るい映像）
  {
    file: "scene_T2_C09_wan21.mp4",
    durationInFrames: 30,
    render: (frame: number) => {
      const text = "未来の私は笑ってるよ";
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-start", paddingTop: 180, paddingLeft: 56 }}>
          <div style={{
            fontSize: 72,
            fontWeight: 300,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#2A2A2A",
            letterSpacing: "0.1em",
          }}>
            {animC(frame, text, 3)}
          </div>
        </AbsoluteFill>
      );
    },
  },
  // C10: CTA（1.6s = 48f）— P3 上部中央
  {
    file: "scene_T2_C10_wan21.mp4",
    durationInFrames: 48,
    render: (frame: number) => {
      const text = "過去の自分にありがとう";
      const fontSize = calcFontSize(text, 10, 72);
      return (
        <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 140 }}>
          <div style={{
            fontSize,
            fontWeight: 800,
            fontFamily: "Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif",
            color: "#FFFFFF",
            textShadow: "0 2px 16px rgba(0,0,0,0.7), 0 0 8px rgba(0,0,0,0.4)",
            letterSpacing: "0.02em",
            whiteSpace: "nowrap" as const,
          }}>
            {animC(frame, text, 3)}
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
    return Math.max(o, interpolate(dist, [0, FLASH_FRAMES], [0.7, 0], { extrapolateRight: "clamp" }));
  }, 0);
  if (opacity === 0) return null;
  return <AbsoluteFill style={{ backgroundColor: `rgba(255,255,255,${opacity})`, zIndex: 10 }} />;
};

// ===== メインコンポーネント =====
export const AdVideoT2: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Audio src={staticFile("bgm_t2.mp3")} volume={0.15} />
      <Sequence from={30}>
        <Audio src={staticFile("narration_t2.wav")} volume={0.4} />
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

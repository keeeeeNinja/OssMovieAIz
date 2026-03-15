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
const clips: {
  file?: string;
  durationInFrames: number;
  render?: (frame: number) => React.ReactNode;
}[] = [
  // Scene 1 — タイトル（黒バック・3秒）P10 筆書き風
  {
    durationInFrames: 90,
    render: (frame: number) => (
      <AbsoluteFill style={{ backgroundColor: "black", justifyContent: "center", alignItems: "center" }}>
        <div style={{
          fontSize: 96,
          fontWeight: 900,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "-0.02em",
          lineHeight: 1.1,
          color: "#F5E6C8",
          textAlign: "center" as const,
        }}>
          {animC(frame, "とんかつ のまど", 15)}
        </div>
      </AbsoluteFill>
    ),
  },
  // Scene 2 — 疲れた日常（5秒）P1 下部左寄せ太ゴシック
  {
    file: "scene2.mp4",
    durationInFrames: 152,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        paddingBottom: 140,
        paddingLeft: 56,
      }}>
        <div style={{
          fontSize: 80,
          fontWeight: 700,
          fontFamily: "Hiragino Sans, sans-serif",
          letterSpacing: "0.02em",
          lineHeight: 1.3,
          color: "#FFFFFF",
          textShadow: "0 2px 24px rgba(0,0,0,0.7)",
        }}>
          {animC(frame, "今日も、お疲れ様。")}
        </div>
      </AbsoluteFill>
    ),
  },
  // Scene 3 — 暖簾の誘い（5秒）テロップなし
  {
    file: "scene3.mp4",
    durationInFrames: 152,
  },
  // Scene 4 — 職人の衣付け（5秒）テロップなし
  {
    file: "scene4.mp4",
    durationInFrames: 152,
  },
  // Scene 5 — 油に投入（5秒）テロップなし
  {
    file: "scene5.mp4",
    durationInFrames: 152,
  },
  // Scene 6 — 揚げ中の臨場感（5秒）テロップなし
  {
    file: "scene6.mp4",
    durationInFrames: 152,
  },
  // Scene 7 — 黄金の断面（5秒）P4 縦書き端配置
  {
    file: "scene7.mp4",
    durationInFrames: 152,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "center",
        alignItems: "flex-start",
        paddingLeft: 64,
      }}>
        <div style={{
          writingMode: "vertical-rl" as const,
          fontSize: 72,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.3em",
          lineHeight: 1,
          color: "#F5E6C8",
          textShadow: "0 1px 16px rgba(0,0,0,0.4)",
        }}>
          {animC(frame, "この断面が、すべて")}
        </div>
      </AbsoluteFill>
    ),
  },
  // Scene 8 — 至福の定食（5秒）P8 下部帯テキスト
  {
    file: "scene8.mp4",
    durationInFrames: 152,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "stretch",
        opacity: interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" }),
        transform: `translateY(${interpolate(frame, [0, 20], [40, 0], { extrapolateRight: "clamp" })}px)`,
      }}>
        <div style={{
          backgroundColor: "rgba(0,0,0,0.45)",
          paddingTop: 20,
          paddingBottom: 28,
          paddingLeft: 48,
          paddingRight: 48,
          textAlign: "center" as const,
        }}>
          <div style={{
            fontSize: 52,
            fontWeight: 500,
            fontFamily: "Hiragino Sans, sans-serif",
            letterSpacing: "0.18em",
            color: "#FFFFFF",
            display: "flex",
            justifyContent: "center",
          }}>
            {animC(frame, "特選ロースかつ定食", 10)}
          </div>
        </div>
      </AbsoluteFill>
    ),
  },
  // Scene 9 — 箸上げ（5秒）テロップなし
  {
    file: "scene9.mp4",
    durationInFrames: 152,
  },
  // Scene 10 — 満足の笑顔（5秒）P2 中央ブランドロゴ型（下部配置）
  {
    file: "scene10.mp4",
    durationInFrames: 152,
    render: (frame: number) => (
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 200,
      }}>
        <div style={{
          fontSize: 80,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.2em",
          color: "#2C1810",
        }}>
          {animC(frame, "しあわせの、一口")}
        </div>
      </AbsoluteFill>
    ),
  },
  // Scene 11 — 店の外観（5秒）テロップなし
  {
    file: "scene11.mp4",
    durationInFrames: 152,
  },
  // Scene 12 — エンドカード（黒バック・7秒）P10 筆書き風
  {
    durationInFrames: 210,
    render: (frame: number) => (
      <AbsoluteFill style={{ backgroundColor: "black", justifyContent: "center", alignItems: "center" }}>
        <div style={{ textAlign: "center" as const }}>
          <div style={{
            fontSize: 96,
            fontWeight: 900,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            letterSpacing: "-0.02em",
            lineHeight: 1.1,
            color: "#F5E6C8",
            marginBottom: 48,
          }}>
            {animC(frame, "とんかつ のまど", 15)}
          </div>
          <div style={{
            fontSize: 36,
            fontWeight: 300,
            fontFamily: "Hiragino Sans, sans-serif",
            letterSpacing: "0.1em",
            lineHeight: 2,
            color: "rgba(255,255,255,0.7)",
          }}>
            {animC(frame, "ご予約・お問い合わせはこちら", 50)}
          </div>
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
      <Audio src={staticFile("bgm.mp3")} volume={0.35} />
      <Sequence from={90}>
        <Audio src={staticFile("narration.wav")} volume={0.5} />
      </Sequence>
      {clips.map((clip, idx) => {
        const start = from;
        from += clip.durationInFrames;
        return (
          <Sequence key={idx} from={start} durationInFrames={clip.durationInFrames}>
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
      <WhiteFlash />
    </AbsoluteFill>
  );
};

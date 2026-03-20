import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const CHROMATIC_DURATION = 150; // 5秒

// クロマティックアベレーション（色収差）エフェクト
// RGBチャンネルをそれぞれ微妙にずらしてグリッチ感を演出

export const ChromaticEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const D = durationInFrames;

  // オフセット量：最初と最後にグリッチが強くなり、中盤は穏やか（比率で計算）
  const glitchIntensity = interpolate(
    frame,
    [0, D * 0.10, D * 0.27, D * 0.73, D * 0.90, D],
    [0, 12, 4, 4, 12, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // ランダムっぽい揺らぎ（フレームベースで決定論的）
  const jitter = Math.sin(frame * 1.7) * 0.3 + Math.sin(frame * 3.1) * 0.15;
  const offset = glitchIntensity * (1 + jitter);

  // 時々強いグリッチが入る（決定論的）
  const isGlitchFrame =
    frame % 23 < 2 || frame % 37 < 3 || frame % 17 < 1;
  const finalOffset = isGlitchFrame ? offset * 3.5 : offset;

  // Y方向の微妙なずれ（収差はX方向が主だがYも少し）
  const yOffset = finalOffset * 0.15;

  // フェードイン・アウト
  const opacity = interpolate(
    frame,
    [0, 8, D - 8, D],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const videoStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover" as const,
    position: "absolute" as const,
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "black", opacity }}>
      {/* ベース動画（グリーンチャンネル基準・中央） */}
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={videoStyle}
      />

      {/* レッドチャンネル：左にずれ */}
      <div style={{
        position: "absolute",
        width: "100%",
        height: "100%",
        transform: `translate(${-finalOffset}px, ${-yOffset}px)`,
        mixBlendMode: "screen",
        opacity: 0.75,
      }}>
        <OffthreadVideo
          src={staticFile("scene1_lipgloss.mp4")}
          style={{
            ...videoStyle,
            filter: "saturate(300%) hue-rotate(-30deg) brightness(0.6)",
          }}
        />
      </div>

      {/* ブルーチャンネル：右にずれ */}
      <div style={{
        position: "absolute",
        width: "100%",
        height: "100%",
        transform: `translate(${finalOffset}px, ${yOffset}px)`,
        mixBlendMode: "screen",
        opacity: 0.75,
      }}>
        <OffthreadVideo
          src={staticFile("scene1_lipgloss.mp4")}
          style={{
            ...videoStyle,
            filter: "saturate(300%) hue-rotate(200deg) brightness(0.6)",
          }}
        />
      </div>

      {/* 強いグリッチ時の白フラッシュ */}
      {isGlitchFrame && (
        <AbsoluteFill style={{
          backgroundColor: `rgba(255,255,255,${glitchIntensity * 0.02})`,
        }} />
      )}
    </AbsoluteFill>
  );
};

import React, { useEffect, useRef } from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { lipParticles } from "../data/lipParticles";

// ===== アニメーション設定 =====
const SCATTER_FRAMES = 15;   // 散乱（0.5秒）
const CONVERGE_FRAMES = 90;  // 収束（3秒）
const HOLD_FRAMES = 45;      // 商品表示（1.5秒）
export const LIP_PARTICLE_DURATION = SCATTER_FRAMES + CONVERGE_FRAMES + HOLD_FRAMES; // 150f = 5秒

const CANVAS_W = 1080;
const CANVAS_H = 1920;

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export const LipParticleEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    const rawProgress = interpolate(
      frame,
      [SCATTER_FRAMES, SCATTER_FRAMES + CONVERGE_FRAMES],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const t = easeInOutCubic(rawProgress);

    // パーティクルのフェードアウト（収束75%時点から消え始める）
    const particleAlpha = interpolate(
      frame,
      [SCATTER_FRAMES + CONVERGE_FRAMES * 0.75, SCATTER_FRAMES + CONVERGE_FRAMES],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    lipParticles.forEach((p) => {
      const x = (p.sx + (p.tx - p.sx) * t) * CANVAS_W;
      const y = (p.sy + (p.ty - p.sy) * t) * CANVAS_H;

      // 収束するほど実際の色に近づく（散乱中は白く光る）
      const r = Math.round(255 + (p.r - 255) * t);
      const g = Math.round(255 + (p.g - 255) * t);
      const b = Math.round(255 + (p.b - 255) * t);

      // 収束時のサイズ（小さめに調整）
      const size = p.size * (0.3 + t * 1.5);
      const alpha = (0.3 + t * 0.7) * particleAlpha;

      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
      ctx.fill();
    });

    // 収束後のグロー
    if (t > 0.6) {
      const glowAlpha = interpolate(t, [0.6, 1], [0, 0.12]) * particleAlpha;
      const grad = ctx.createRadialGradient(CANVAS_W / 2, CANVAS_H * 0.4, 0, CANVAS_W / 2, CANVAS_H * 0.4, CANVAS_W * 0.5);
      grad.addColorStop(0, `rgba(255, 200, 210, ${glowAlpha})`);
      grad.addColorStop(1, "rgba(255, 200, 210, 0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
    }
  }, [frame]);

  // 動画：収束75%時点からふわっとフェードイン、収束完了で完全表示
  const videoOpacity = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES * 0.75, SCATTER_FRAMES + CONVERGE_FRAMES],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // キネティックタイポグラフィ
  // 収束50%時点から1文字ずつ登場、収束完了まで全文字が揃う
  const TEXT = "艶やかな彩り";
  const TEXT_START = SCATTER_FRAMES + CONVERGE_FRAMES * 0.5; // 収束50%から開始
  const TEXT_END = SCATTER_FRAMES + CONVERGE_FRAMES * 0.95;  // 収束95%で全文字揃う
  const charInterval = (TEXT_END - TEXT_START) / TEXT.length;

  const textChars = TEXT.split("").map((char, i) => {
    const charStart = TEXT_START + i * charInterval;
    const charEnd = charStart + 20; // 20フレームかけて1文字登場

    const charProgress = interpolate(frame, [charStart, charEnd], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

    const opacity = charProgress;
    const translateY = interpolate(charProgress, [0, 1], [40, 0]);

    return (
      <span
        key={i}
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        }}
      >
        {char}
      </span>
    );
  });

  return (
    <AbsoluteFill>
      {/* Layer 1: ピンク背景グラデーション（動画の背景色を近似） */}
      <AbsoluteFill style={{
        background: "linear-gradient(160deg, rgb(158,105,104) 0%, rgb(185,138,136) 40%, rgb(210,172,170) 100%)",
      }} />

      {/* Layer 2: パーティクル */}
      <canvas
        ref={canvasRef}
        width={CANVAS_W}
        height={CANVAS_H}
        style={{ position: "absolute", width: "100%", height: "100%" }}
      />

      {/* Layer 3: 元動画（収束75%からふわっとフェードイン） */}
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: videoOpacity,
        }}
      />

      {/* Layer 4: キネティックタイポグラフィ */}
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 180,
      }}>
        <div style={{
          fontSize: 72,
          fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.25em",
          color: "#2C1A1D",
          textShadow: "0 2px 20px rgba(100, 40, 60, 0.4)",
          display: "flex",
        }}>
          {textChars}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

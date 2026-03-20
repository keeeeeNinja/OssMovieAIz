import React, { useEffect, useRef } from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const LENS_FLARE_DURATION = 150; // 5秒

// シード付き乱数
function seededRng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// フレア発光源：ボトルキャップ付近（画面上部中央）
const FLARE_X = 0.5;
const FLARE_Y = 0.12;

// 光の筋（ストリーク）の設定
const STREAKS = (() => {
  const rng = seededRng(99);
  return Array.from({ length: 12 }, (_, i) => ({
    angle: (i / 12) * Math.PI * 2,
    length: 0.15 + rng() * 0.25,
    width: 1 + rng() * 3,
    hue: rng() < 0.5 ? 320 + rng() * 40 : 45 + rng() * 20,
  }));
})();

// フレアゴースト（レンズ内の二次反射）
const GHOSTS = [
  { offset: 0.3, size: 0.04, hue: 200 },
  { offset: 0.55, size: 0.07, hue: 320 },
  { offset: 0.8, size: 0.03, hue: 45 },
  { offset: 1.1, size: 0.09, hue: 160 },
  { offset: 1.5, size: 0.05, hue: 280 },
];

function drawBloom(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  alpha: number
) {
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
  grad.addColorStop(0, `rgba(255, 255, 255, ${alpha})`);
  grad.addColorStop(0.15, `rgba(255, 220, 240, ${alpha * 0.8})`);
  grad.addColorStop(0.4, `rgba(255, 180, 220, ${alpha * 0.3})`);
  grad.addColorStop(1, `rgba(255, 180, 220, 0)`);
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fill();
}

function drawStreak(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  angle: number,
  length: number,
  width: number,
  hue: number,
  alpha: number,
  W: number,
  H: number
) {
  const diag = Math.sqrt(W * W + H * H);
  const ex = cx + Math.cos(angle) * diag * length;
  const ey = cy + Math.sin(angle) * diag * length;

  const grad = ctx.createLinearGradient(cx, cy, ex, ey);
  grad.addColorStop(0, `hsla(${hue}, 100%, 95%, ${alpha})`);
  grad.addColorStop(0.3, `hsla(${hue}, 100%, 90%, ${alpha * 0.4})`);
  grad.addColorStop(1, `hsla(${hue}, 100%, 90%, 0)`);

  ctx.save();
  ctx.lineWidth = width;
  ctx.strokeStyle = grad;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(ex, ey);
  ctx.stroke();
  ctx.restore();
}

export const LensFlareEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, width, height);

    const cx = FLARE_X * width;
    const cy = FLARE_Y * height;

    // アニメーション：最初にフレアが出て、徐々に安定
    const flareIn = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const flareOut = interpolate(frame, [LENS_FLARE_DURATION - 25, LENS_FLARE_DURATION], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const baseAlpha = flareIn * flareOut;

    // 呼吸するようなパルス（ゆっくりきらめく）
    const pulse = 0.75 + 0.25 * Math.sin(frame * 0.08);
    const alpha = baseAlpha * pulse;

    // ブルーム（中心発光）
    drawBloom(ctx, cx, cy, width * 0.5, alpha * 0.18);
    drawBloom(ctx, cx, cy, width * 0.15, alpha * 0.5);
    drawBloom(ctx, cx, cy, width * 0.05, alpha * 0.9);

    // 光の筋
    STREAKS.forEach((s) => {
      drawStreak(ctx, cx, cy, s.angle, s.length, s.width, s.hue, alpha * 0.7, width, height);
    });

    // フレアゴースト（レンズ反射の二次光）
    // 発光源から逆方向に並ぶ
    const screenCx = width * 0.5;
    const screenCy = height * 0.5;
    GHOSTS.forEach((g) => {
      const gx = cx + (screenCx - cx) * g.offset * 2;
      const gy = cy + (screenCy - cy) * g.offset * 2;
      const r = width * g.size;
      const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, r);
      grad.addColorStop(0, `hsla(${g.hue}, 80%, 90%, ${alpha * 0.35})`);
      grad.addColorStop(0.5, `hsla(${g.hue}, 80%, 80%, ${alpha * 0.15})`);
      grad.addColorStop(1, `hsla(${g.hue}, 80%, 80%, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(gx, gy, r, 0, Math.PI * 2);
      ctx.fill();
    });

    // 中心の強いホワイトコア
    const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, width * 0.025);
    core.addColorStop(0, `rgba(255,255,255,${alpha * 0.95})`);
    core.addColorStop(1, `rgba(255,255,255,0)`);
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, width * 0.025, 0, Math.PI * 2);
    ctx.fill();
  }, [frame, width, height]);

  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ position: "absolute", width: "100%", height: "100%" }}
      />
    </AbsoluteFill>
  );
};

import React, { useEffect, useRef } from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { bottleParticles } from "../data/bottleParticles";

// ===== アニメーション設定 =====
const SCATTER_FRAMES = 30;   // 散らばった状態を維持（1秒）
const CONVERGE_FRAMES = 120; // 収束アニメーション（4秒）
const HOLD_FRAMES = 60;      // 完成状態を保持（2秒）
export const PARTICLE_BOTTLE_DURATION = SCATTER_FRAMES + CONVERGE_FRAMES + HOLD_FRAMES; // 210f = 7秒

const CANVAS_W = 1080;
const CANVAS_H = 1920;

// イーズ関数（ease-in-out cubic）
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export const ParticleBottle: React.FC = () => {
  const frame = useCurrentFrame();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    // 収束の進行度（0 = 散乱、1 = 収束完了）
    const rawProgress = interpolate(
      frame,
      [SCATTER_FRAMES, SCATTER_FRAMES + CONVERGE_FRAMES],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const t = easeInOutCubic(rawProgress);

    // 完成後のフェードイン
    const converged = frame >= SCATTER_FRAMES + CONVERGE_FRAMES;

    bottleParticles.forEach((p) => {
      const x = (p.sx + (p.tx - p.sx) * t) * CANVAS_W;
      const y = (p.sy + (p.ty - p.sy) * t) * CANVAS_H;

      // 収束に従ってサイズが拡大（収束後はドット抜けを埋めるため大きめに）
      const size = p.size * (0.4 + t * 2.2);
      const alpha = 0.25 + t * 0.75;

      // 水滴のような青白いカラー、収束するほど透明感が増す
      const lightness = Math.round(75 + t * 15);
      const saturation = Math.round(60 + t * 30);

      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${200 + p.hue}, ${saturation}%, ${lightness}%, ${alpha})`;
      ctx.fill();
    });

    // 収束後：中心に光のグロー
    if (t > 0.5) {
      const glowAlpha = interpolate(t, [0.5, 1], [0, 0.15]);
      const grad = ctx.createRadialGradient(
        CANVAS_W / 2, CANVAS_H / 2, 0,
        CANVAS_W / 2, CANVAS_H / 2, CANVAS_W * 0.6
      );
      grad.addColorStop(0, `rgba(180, 240, 255, ${glowAlpha})`);
      grad.addColorStop(1, "rgba(180, 240, 255, 0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
    }
  }, [frame]);

  // ボトル画像：収束完了後にフェードイン（パーティクルと重ならないようにHOLD区間で登場）
  const bottleOpacity = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES, SCATTER_FRAMES + CONVERGE_FRAMES + 30],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // パーティクル：収束完了後にフェードアウト
  const particleLayerOpacity = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES, SCATTER_FRAMES + CONVERGE_FRAMES + 30],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#06101a" }}>
      {/* パーティクルレイヤー（収束後フェードアウト） */}
      <canvas
        ref={canvasRef}
        width={CANVAS_W}
        height={CANVAS_H}
        style={{ position: "absolute", width: "100%", height: "100%", opacity: particleLayerOpacity }}
      />

      {/* ボトル画像（収束完了後にクリーンにフェードイン） */}
      <Img
        src={staticFile("kosui.png")}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: "center center",
          opacity: bottleOpacity,
        }}
      />
    </AbsoluteFill>
  );
};

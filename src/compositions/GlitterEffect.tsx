import React, { useEffect, useRef } from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ===== 設定 =====
const NUM_GLITTERS = 180;
export const GLITTER_DURATION = 150; // 5秒（元動画に合わせる）

// ===== シード付き乱数 =====
function seededRng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// ===== グリッター粒子の初期データ（モジュールレベルで固定） =====
type Glitter = {
  x: number;       // 初期X位置 [0-1]
  y: number;       // 初期Y位置 [-0.2 - 0] 画面上から降る
  vx: number;      // X速度
  vy: number;      // Y速度（落下）
  size: number;    // 粒サイズ px
  rotation: number; // 初期回転角
  rotSpeed: number; // 回転速度
  hue: number;     // 色相（ピンク〜ゴールド系）
  delay: number;   // 出現フレーム遅延
  twinkle: number; // きらめき周期
};

const glitters: Glitter[] = (() => {
  const rng = seededRng(2024);
  return Array.from({ length: NUM_GLITTERS }, () => ({
    x: rng(),
    y: -rng() * 0.3,
    vx: (rng() - 0.5) * 0.003,
    vy: 0.003 + rng() * 0.005,
    size: 4 + rng() * 10,
    rotation: rng() * Math.PI * 2,
    rotSpeed: (rng() - 0.5) * 0.15,
    hue: rng() < 0.5
      ? 320 + rng() * 40   // ピンク〜マゼンタ
      : 40 + rng() * 20,   // ゴールド
    delay: Math.floor(rng() * 60),
    twinkle: 0.05 + rng() * 0.1,
  }));
})();

// ===== グリッター1個を描画（ひし形） =====
function drawGlitter(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  rotation: number,
  hue: number,
  alpha: number
) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rotation);
  ctx.globalAlpha = alpha;

  // 光沢グラデーション
  const grad = ctx.createLinearGradient(-size, 0, size, 0);
  grad.addColorStop(0, `hsla(${hue}, 100%, 95%, 0)`);
  grad.addColorStop(0.3, `hsla(${hue}, 100%, 90%, 1)`);
  grad.addColorStop(0.5, `hsla(${hue}, 60%, 100%, 1)`); // 中心は白
  grad.addColorStop(0.7, `hsla(${hue}, 100%, 90%, 1)`);
  grad.addColorStop(1, `hsla(${hue}, 100%, 95%, 0)`);

  // ひし形（横長の星型）
  ctx.beginPath();
  ctx.moveTo(0, -size * 0.35);
  ctx.lineTo(size, 0);
  ctx.lineTo(0, size * 0.35);
  ctx.lineTo(-size, 0);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // 縦長のハイライト
  const grad2 = ctx.createLinearGradient(0, -size * 0.35, 0, size * 0.35);
  grad2.addColorStop(0, `hsla(${hue}, 80%, 100%, 0)`);
  grad2.addColorStop(0.5, `hsla(${hue}, 60%, 100%, 0.6)`);
  grad2.addColorStop(1, `hsla(${hue}, 80%, 100%, 0)`);
  ctx.beginPath();
  ctx.moveTo(0, -size * 0.35);
  ctx.lineTo(size * 0.2, 0);
  ctx.lineTo(0, size * 0.35);
  ctx.lineTo(-size * 0.2, 0);
  ctx.closePath();
  ctx.fillStyle = grad2;
  ctx.fill();

  ctx.restore();
}

// ===== メインコンポーネント =====
export const GlitterEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, width, height);

    // 全体フェードイン・アウト
    const globalAlpha = interpolate(
      frame,
      [0, 15, GLITTER_DURATION - 20, GLITTER_DURATION],
      [0, 1, 1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );

    glitters.forEach((g) => {
      const f = frame - g.delay;
      if (f < 0) return;

      // 位置
      const px = (g.x + g.vx * f) * width;
      const py = (g.y + g.vy * f) * height;

      // 画面外に出たらスキップ
      if (py > height + 20) return;

      // 回転
      const rot = g.rotation + g.rotSpeed * f;

      // きらめき（サイン波で明滅）
      const twinkle = 0.5 + 0.5 * Math.sin(f * g.twinkle * Math.PI * 2);
      const alpha = globalAlpha * (0.4 + twinkle * 0.6);

      drawGlitter(ctx, px, py, g.size, rot, g.hue, alpha);
    });
  }, [frame, width, height]);

  return (
    <AbsoluteFill>
      {/* 元動画 */}
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />

      {/* グリッターレイヤー */}
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ position: "absolute", width: "100%", height: "100%" }}
      />
    </AbsoluteFill>
  );
};

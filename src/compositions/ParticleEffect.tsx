import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// ============================================================
// particles.js JSON設定から変換
// color: 8色の金・白系、shape: star(2/3) + circle(1/3)
// move: direction=bottom, speed≈2.5, random
// opacity: anim speed=8, min=0, max=1, random
// size: anim speed=10, min=0.3, max=5, random
// ============================================================

const W = 1080;
const H = 1920;
const COUNT = 300;

const COLORS = [
  "#ffffff", "#ffe066", "#ffd700", "#fff5cc",
  "#fffacd", "#ffec80", "#f0f0f0", "#ffe599",
];

// ["star","circle","star"] → star 2/3, circle 1/3
const SHAPE_POOL = ["star", "star", "circle"] as const;

// シード付き乱数（決定論的）
const rand = (seed: number) => {
  const s = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};

interface Particle {
  x: number;
  y0: number;
  color: string;
  shape: "star" | "circle";
  maxSize: number;   // 0.3 〜 5.0
  speed: number;     // px/frame（direction: bottom）
  oPhase: number;    // opacity oscillation phase
  sPhase: number;    // size oscillation phase
}

// 粒子データはコンポーネント外で一度だけ生成（変化しない）
const PARTICLES: Particle[] = Array.from({ length: COUNT }, (_, i) => ({
  x:       rand(i * 9 + 1) * W,
  y0:      rand(i * 9 + 2) * H,
  color:   COLORS[Math.floor(rand(i * 9 + 3) * COLORS.length)],
  shape:   SHAPE_POOL[Math.floor(rand(i * 9 + 4) * 3)],
  maxSize: 0.3 + rand(i * 9 + 5) * 4.7,          // 0.3 〜 5.0
  speed:   1.0 + rand(i * 9 + 6) * 3.0,           // ~2.5 中心にばらつき
  oPhase:  rand(i * 9 + 7) * Math.PI * 2,
  sPhase:  rand(i * 9 + 8) * Math.PI * 2,
}));

// 5角星のSVGポリゴン
const Star: React.FC<{ cx: number; cy: number; r: number; fill: string; opacity: number }> = ({
  cx, cy, r, fill, opacity,
}) => {
  const inner = r * 0.4;
  const n = 5;
  const pts = Array.from({ length: n * 2 }, (_, i) => {
    const angle = (i * Math.PI) / n - Math.PI / 2;
    const radius = i % 2 === 0 ? r : inner;
    return `${cx + Math.cos(angle) * radius},${cy + Math.sin(angle) * radius}`;
  }).join(" ");
  return <polygon points={pts} fill={fill} opacity={opacity} />;
};

export const ParticleEffect: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg
        width={W}
        height={H}
        style={{ position: "absolute", inset: 0 }}
        overflow="hidden"
      >
        {PARTICLES.map((p, i) => {
          // 下方向に移動、画面外に出たら上から再登場（ループ）
          const y = ((p.y0 + frame * p.speed) % H + H) % H;

          // opacity: speed=8 → 約 2π/(8/60*30) ≈ 0.07 rad/frame
          const opacity = (Math.sin(frame * 0.07 + p.oPhase) + 1) / 2;

          // size: speed=10 → 約 0.087 rad/frame
          const sizeT = (Math.sin(frame * 0.087 + p.sPhase) + 1) / 2;
          const size = 0.3 + (p.maxSize - 0.3) * sizeT;

          return p.shape === "star" ? (
            <Star key={i} cx={p.x} cy={y} r={size} fill={p.color} opacity={opacity} />
          ) : (
            <circle key={i} cx={p.x} cy={y} r={size} fill={p.color} opacity={opacity} />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

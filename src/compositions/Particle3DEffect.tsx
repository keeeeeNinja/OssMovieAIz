import React from "react";
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { lipParticles } from "../data/lipParticles";

// ===== アニメーション設定 =====
const SCATTER_FRAMES = 0;
const CONVERGE_FRAMES = 105;
const HOLD_FRAMES = 45;
export const PARTICLE_3D_DURATION = SCATTER_FRAMES + CONVERGE_FRAMES + HOLD_FRAMES;

// ===== シード付き乱数 =====
function seededRng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

// ===== 3Dパーティクルデータ（モジュールレベルで固定） =====
const rng = seededRng(999);
const particleData = lipParticles.map((p) => ({
  // 収束先：2D座標を3D空間にマッピング（Z=0の平面）
  tx: (p.tx - 0.5) * 4.0,
  ty: -(p.ty - 0.5) * 7.0,
  tz: 0,
  // 散乱開始位置（3D空間にランダム配置）
  sx: (rng() - 0.5) * 10,
  sy: (rng() - 0.5) * 14,
  sz: (rng() - 0.5) * 12,
  r: p.r / 255,
  g: p.g / 255,
  b: p.b / 255,
  size: p.size,
}));

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// ===== カメラコントローラー =====
const CameraController: React.FC<{ t: number }> = ({ t }) => {
  const { camera } = useThree();

  // 収束するにつれてカメラが正面に移動
  camera.position.x = Math.sin((1 - t) * 0.5) * 3;
  camera.position.y = (1 - t) * 1;
  camera.position.z = 10 - t * 2.5;
  camera.lookAt(0, 0, 0);

  return null;
};

// ===== 3Dパーティクル =====
const Particles: React.FC<{ t: number; opacity: number }> = ({ t, opacity }) => {
  // フレームごとに新しい配列を作成（確実に更新される）
  const count = particleData.length;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);

  particleData.forEach((p, i) => {
    positions[i * 3]     = p.sx + (p.tx - p.sx) * t;
    positions[i * 3 + 1] = p.sy + (p.ty - p.sy) * t;
    positions[i * 3 + 2] = p.sz + (p.tz - p.sz) * t;

    // 散乱中は白く光り、収束で本来の色へ
    colors[i * 3]     = 1 + (p.r - 1) * t;
    colors[i * 3 + 1] = 1 + (p.g - 1) * t;
    colors[i * 3 + 2] = 1 + (p.b - 1) * t;
  });

  const posAttr = new THREE.BufferAttribute(positions, 3);
  const colAttr = new THREE.BufferAttribute(colors, 3);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", posAttr);
  geometry.setAttribute("color", colAttr);

  const material = new THREE.PointsMaterial({
    vertexColors: true,
    transparent: true,
    opacity,
    sizeAttenuation: true, // 奥行きで大きさが変わる（遠近感）
    size: 0.05 + t * 0.02, // 収束するにつれて少し大きく
    depthWrite: false,
  });

  return <primitive object={new THREE.Points(geometry, material)} />;
};

// ===== メインコンポーネント =====
export const Particle3DEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const rawProgress = interpolate(
    frame,
    [SCATTER_FRAMES, SCATTER_FRAMES + CONVERGE_FRAMES],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const t = easeInOutCubic(rawProgress);

  const particleOpacity = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES * 0.75, SCATTER_FRAMES + CONVERGE_FRAMES],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const videoOpacity = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES * 0.75, SCATTER_FRAMES + CONVERGE_FRAMES],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // キネティックタイポグラフィ
  const TEXT = "艶やかな彩り";
  const TEXT_START = SCATTER_FRAMES + CONVERGE_FRAMES * 0.5;
  const TEXT_END = SCATTER_FRAMES + CONVERGE_FRAMES * 0.95;
  const charInterval = (TEXT_END - TEXT_START) / TEXT.length;

  const textChars = TEXT.split("").map((char, i) => {
    const charStart = TEXT_START + i * charInterval;
    const progress = interpolate(frame, [charStart, charStart + 20], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return (
      <span key={i} style={{
        opacity: progress,
        transform: `translateY(${interpolate(progress, [0, 1], [40, 0])}px)`,
        display: "inline-block",
      }}>
        {char}
      </span>
    );
  });

  return (
    <AbsoluteFill>
      {/* Layer 1: ピンク背景 */}
      <AbsoluteFill style={{
        background: "linear-gradient(160deg, rgb(158,105,104) 0%, rgb(185,138,136) 40%, rgb(210,172,170) 100%)",
      }} />

      {/* Layer 2: Three.js 3Dパーティクル */}
      <AbsoluteFill>
        <ThreeCanvas width={width} height={height}>
          <CameraController t={t} />
          <Particles t={t} opacity={particleOpacity} />
        </ThreeCanvas>
      </AbsoluteFill>

      {/* Layer 3: 元動画 */}
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
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 180 }}>
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

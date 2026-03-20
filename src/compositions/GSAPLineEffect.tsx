import React, { useEffect, useRef } from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { gsap } from "gsap";
import { lipParticles } from "../data/lipParticles";

export const GSAP_LINE_DURATION = 150; // 5秒

// ===== アニメーション設定 =====
const SCATTER_FRAMES = 15;
const CONVERGE_FRAMES = 90;

// ===== テキスト =====
const TEXT = "艶やかな彩り";
const TEXT_START = SCATTER_FRAMES + CONVERGE_FRAMES * 0.5;
const TEXT_END = SCATTER_FRAMES + CONVERGE_FRAMES * 0.95;

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// ===== SVGパスの設計 =====
// テキスト下に3本のラインが中央から広がる演出
// Canvas 1080×1920, テキスト位置: 下から180px = y≈1740
const CX = 540; // 中央X
const LINE_Y = 1780; // ラインのY位置（テキスト直下）
const LINE_HALF_W = 360; // ラインの半幅（両側に伸びる）
// パス: 中央から左右に伸びるライン（左端→中央→右端）
const MAIN_PATH = `M ${CX - LINE_HALF_W} ${LINE_Y} L ${CX + LINE_HALF_W} ${LINE_Y}`;
const MAIN_PATH_LENGTH = LINE_HALF_W * 2; // = 720px

// サブライン（メインの上下に細く）
const SUB_Y1 = LINE_Y - 12;
const SUB_Y2 = LINE_Y + 12;
const SUB_HALF_W = 200;
const SUB_PATH_1 = `M ${CX - SUB_HALF_W} ${SUB_Y1} L ${CX + SUB_HALF_W} ${SUB_Y1}`;
const SUB_PATH_2 = `M ${CX - SUB_HALF_W} ${SUB_Y2} L ${CX + SUB_HALF_W} ${SUB_Y2}`;
const SUB_PATH_LENGTH = SUB_HALF_W * 2; // = 400px

export const GSAPLineEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // GSAPタイムラインのref
  const mainTlRef = useRef<gsap.core.Timeline | null>(null);
  const subTlRef = useRef<gsap.core.Timeline | null>(null);

  const mainPathRef = useRef<SVGPathElement>(null);
  const subPath1Ref = useRef<SVGPathElement>(null);
  const subPath2Ref = useRef<SVGPathElement>(null);
  const diamondRef = useRef<SVGPolygonElement>(null);

  // マウント時にGSAPタイムラインを構築
  useEffect(() => {
    if (!mainPathRef.current || !subPath1Ref.current || !subPath2Ref.current) return;

    // メインライン: 中央から左右に広がるように見せる
    // strokeDasharray = 全長、strokeDashoffset = 全長→0 でラインが描かれる
    mainPathRef.current.style.strokeDasharray = `${MAIN_PATH_LENGTH}`;
    mainPathRef.current.style.strokeDashoffset = `${MAIN_PATH_LENGTH}`;
    subPath1Ref.current.style.strokeDasharray = `${SUB_PATH_LENGTH}`;
    subPath1Ref.current.style.strokeDashoffset = `${SUB_PATH_LENGTH}`;
    subPath2Ref.current.style.strokeDasharray = `${SUB_PATH_LENGTH}`;
    subPath2Ref.current.style.strokeDashoffset = `${SUB_PATH_LENGTH}`;

    // メインラインタイムライン（2秒）
    const mainTl = gsap.timeline({ paused: true });
    mainTl
      .to(mainPathRef.current, {
        strokeDashoffset: 0,
        duration: 2.5,
        ease: "power2.inOut",
      })
      .to(diamondRef.current, {
        opacity: 1,
        scale: 1,
        duration: 0.4,
        ease: "back.out(2)",
      }, "-=0.3");

    mainTlRef.current = mainTl;

    // サブラインタイムライン（少し遅れて）
    const subTl = gsap.timeline({ paused: true });
    subTl
      .to(subPath1Ref.current, {
        strokeDashoffset: 0,
        duration: 2.2,
        ease: "power3.out",
      })
      .to(subPath2Ref.current, {
        strokeDashoffset: 0,
        duration: 2.2,
        ease: "power3.out",
      }, "<");

    subTlRef.current = subTl;
  }, []);

  // フレームごとにGSAPタイムラインをシーク
  useEffect(() => {
    if (!mainTlRef.current || !subTlRef.current) return;

    // ラインはテキスト登場（TEXT_START）と同タイミングで開始
    const lineFrame = frame - TEXT_START;
    const lineTime = Math.max(0, lineFrame / fps);
    const subDelay = 0.2; // サブラインは少し遅れる

    mainTlRef.current.seek(lineTime);
    subTlRef.current.seek(Math.max(0, lineTime - subDelay));
  }, [frame, fps]);

  // 動画フェードイン
  const videoOpacity = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES * 0.75, SCATTER_FRAMES + CONVERGE_FRAMES],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // パーティクル（Canvas2D、LipParticleEffectと同じロジック）
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rawProgress = interpolate(
    frame,
    [SCATTER_FRAMES, SCATTER_FRAMES + CONVERGE_FRAMES],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const t = easeInOutCubic(rawProgress);
  const particleAlpha = interpolate(
    frame,
    [SCATTER_FRAMES + CONVERGE_FRAMES * 0.75, SCATTER_FRAMES + CONVERGE_FRAMES],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, 1080, 1920);
    lipParticles.forEach((p) => {
      const x = (p.sx + (p.tx - p.sx) * t) * 1080;
      const y = (p.sy + (p.ty - p.sy) * t) * 1920;
      const r = Math.round(255 + (p.r - 255) * t);
      const g = Math.round(255 + (p.g - 255) * t);
      const b = Math.round(255 + (p.b - 255) * t);
      const size = p.size * (0.3 + t * 1.5);
      const alpha = (0.3 + t * 0.7) * particleAlpha;
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
      ctx.fill();
    });
  }, [frame]);

  // キネティックタイポグラフィ
  const charInterval = (TEXT_END - TEXT_START) / TEXT.length;
  const textChars = TEXT.split("").map((char, i) => {
    const charStart = TEXT_START + i * charInterval;
    const progress = interpolate(frame, [charStart, charStart + 20], [0, 1], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });
    return (
      <span key={i} style={{
        opacity: progress,
        transform: `translateY(${interpolate(progress, [0, 1], [40, 0])}px)`,
        display: "inline-block",
      }}>{char}</span>
    );
  });

  return (
    <AbsoluteFill>
      {/* Layer 1: ピンク背景 */}
      <AbsoluteFill style={{
        background: "linear-gradient(160deg, rgb(158,105,104) 0%, rgb(185,138,136) 40%, rgb(210,172,170) 100%)",
      }} />

      {/* Layer 2: パーティクル */}
      <canvas ref={canvasRef} width={1080} height={1920}
        style={{ position: "absolute", width: "100%", height: "100%" }} />

      {/* Layer 3: 元動画 */}
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover", opacity: videoOpacity }}
      />

      {/* Layer 4: キネティックタイポグラフィ */}
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 200 }}>
        <div style={{
          fontSize: 72, fontWeight: 300,
          fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
          letterSpacing: "0.25em", color: "#2C1A1D",
          textShadow: "0 2px 20px rgba(100,40,60,0.4)",
          display: "flex",
        }}>
          {textChars}
        </div>
      </AbsoluteFill>

      {/* Layer 5: GSAPラインアニメーション（SVG） */}
      <svg
        style={{ position: "absolute", width: "100%", height: "100%", overflow: "visible" }}
        viewBox="0 0 1080 1920"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* メインライン */}
        <path
          ref={mainPathRef}
          d={MAIN_PATH}
          stroke="#2C1A1D"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />
        {/* サブライン（上） */}
        <path
          ref={subPath1Ref}
          d={SUB_PATH_1}
          stroke="#2C1A1D"
          strokeWidth="1.5"
          fill="none"
          strokeLinecap="round"
          opacity="0.85"
        />
        {/* サブライン（下） */}
        <path
          ref={subPath2Ref}
          d={SUB_PATH_2}
          stroke="#2C1A1D"
          strokeWidth="1.5"
          fill="none"
          strokeLinecap="round"
          opacity="0.85"
        />
        {/* 中央のダイヤモンドアクセント */}
        <polygon
          ref={diamondRef}
          points={`${CX},${LINE_Y - 6} ${CX + 5},${LINE_Y} ${CX},${LINE_Y + 6} ${CX - 5},${LINE_Y}`}
          fill="#2C1A1D"
          opacity="0"
          style={{ transformOrigin: `${CX}px ${LINE_Y}px`, transform: "scale(0)" }}
        />
      </svg>
    </AbsoluteFill>
  );
};

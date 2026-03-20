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

export const GSAP_MASK_REVEAL_DURATION = 120; // 4秒（動画の長さに合わせる）

// ===== タイミング =====
const VIDEO_FADEIN_START = 0;
const VIDEO_FADEIN_END = 30;

// テキストリビール（フレーム）
const SCAN_START = 10;       // スキャンライン開始
const REVEAL_START = 22;     // メインテキストリビール開始
const SUB_REVEAL_START = 55; // サブテキスト開始
const LABEL_START = 75;      // ラベル開始

const MAIN_TEXT = "艶やかな彩り";
const SUB_TEXT = "新作リップグロス";
const LABEL_TEXT = "NEW ARRIVAL";

export const GSAPMaskRevealEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // ===== タイミング（尺に合わせて比率で自動計算） =====
  const D = durationInFrames;
  const SCAN_START        = Math.round(D * 0.08);
  const REVEAL_START      = Math.round(D * 0.18);
  const SUB_REVEAL_START  = Math.round(D * 0.46);
  const LABEL_START       = Math.round(D * 0.62);
  const VIDEO_FADEIN_END  = Math.min(30, Math.round(D * 0.25));

  // ===== Refs =====
  const scanLineRef = useRef<HTMLDivElement>(null);
  const mainTextRef = useRef<HTMLDivElement>(null);
  const subTextRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLDivElement>(null);
  const mainClipRef = useRef<HTMLDivElement>(null);
  const subClipRef = useRef<HTMLDivElement>(null);
  const labelClipRef = useRef<HTMLDivElement>(null);
  const decorLineRef = useRef<HTMLDivElement>(null);

  // GSAP タイムライン
  const scanTlRef = useRef<gsap.core.Timeline | null>(null);
  const mainTlRef = useRef<gsap.core.Timeline | null>(null);
  const subTlRef = useRef<gsap.core.Timeline | null>(null);
  const labelTlRef = useRef<gsap.core.Timeline | null>(null);
  const decorTlRef = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => {
    if (
      !scanLineRef.current ||
      !mainClipRef.current ||
      !subClipRef.current ||
      !labelClipRef.current ||
      !decorLineRef.current
    ) return;

    // 初期状態
    gsap.set(scanLineRef.current, { x: "-100%", opacity: 1 });
    gsap.set(mainClipRef.current, { clipPath: "inset(0 100% 0 0)" });
    gsap.set(subClipRef.current, { clipPath: "inset(0 100% 0 0)" });
    gsap.set(labelClipRef.current, { clipPath: "inset(0 100% 0 0)" });
    gsap.set(decorLineRef.current, { scaleX: 0, transformOrigin: "left center" });

    // スキャンライン: 左から右へ走り抜ける（translateXで移動）
    const scanTl = gsap.timeline({ paused: true });
    scanTl.to(scanLineRef.current, {
      x: 1280,
      duration: 1.2,
      ease: "power2.inOut",
    }).to(scanLineRef.current, {
      opacity: 0,
      duration: 0.15,
      ease: "power2.in",
    }, "-=0.15");
    scanTlRef.current = scanTl;

    // メインテキストのclipPath（左→右にリビール）
    const mainTl = gsap.timeline({ paused: true });
    mainTl.to(mainClipRef.current, {
      clipPath: "inset(0 0% 0 0)",
      duration: 1.2,
      ease: "power3.inOut",
    });
    mainTlRef.current = mainTl;

    // サブテキスト
    const subTl = gsap.timeline({ paused: true });
    subTl.to(subClipRef.current, {
      clipPath: "inset(0 0% 0 0)",
      duration: 1.0,
      ease: "power3.inOut",
    });
    subTlRef.current = subTl;

    // ラベル
    const labelTl = gsap.timeline({ paused: true });
    labelTl.to(labelClipRef.current, {
      clipPath: "inset(0 0% 0 0)",
      duration: 0.8,
      ease: "power3.inOut",
    });
    labelTlRef.current = labelTl;

    // 装飾ライン（テキスト直下）
    const decorTl = gsap.timeline({ paused: true });
    decorTl.to(decorLineRef.current, {
      scaleX: 1,
      duration: 1.5,
      ease: "power2.out",
    });
    decorTlRef.current = decorTl;
  }, []);

  // フレームごとにシーク
  useEffect(() => {
    const t = (f: number) => Math.max(0, (frame - f) / fps);

    scanTlRef.current?.seek(t(SCAN_START));
    mainTlRef.current?.seek(t(REVEAL_START));
    subTlRef.current?.seek(t(SUB_REVEAL_START));
    labelTlRef.current?.seek(t(LABEL_START));
    decorTlRef.current?.seek(t(REVEAL_START + 10));
  }, [frame, fps]);

  // 動画フェードイン
  const videoOpacity = interpolate(
    frame,
    [0, VIDEO_FADEIN_END],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // オーバーレイ（動画の上に薄い暗幕でテキスト読みやすく）
  const overlayOpacity = interpolate(
    frame,
    [0, VIDEO_FADEIN_END + 20],
    [0, 0.35],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill>
      {/* Layer 1: ピンク背景 */}
      <AbsoluteFill style={{
        background: "linear-gradient(160deg, rgb(158,105,104) 0%, rgb(185,138,136) 40%, rgb(210,172,170) 100%)",
      }} />

      {/* Layer 2: 元動画 */}
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={{
          position: "absolute", width: "100%", height: "100%",
          objectFit: "cover", opacity: videoOpacity,
        }}
      />

      {/* Layer 3: 薄いオーバーレイ（テキスト可読性） */}
      <AbsoluteFill style={{
        background: `rgba(30, 10, 15, ${overlayOpacity})`,
      }} />

      {/* Layer 4: テキスト群（下部に集める） */}
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        paddingBottom: 160,
        paddingLeft: 80,
      }}>

        {/* LABEL */}
        <div ref={labelClipRef} style={{ overflow: "hidden", marginBottom: 16 }}>
          <div ref={labelRef} style={{
            fontSize: 22,
            fontWeight: 600,
            fontFamily: "Hiragino Kaku Gothic ProN, sans-serif",
            letterSpacing: "0.35em",
            color: "#D4A8A0",
          }}>
            {LABEL_TEXT}
          </div>
        </div>

        {/* メインテキスト */}
        <div ref={mainClipRef} style={{ overflow: "hidden", marginBottom: 12 }}>
          <div ref={mainTextRef} style={{
            fontSize: 80,
            fontWeight: 300,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            letterSpacing: "0.2em",
            color: "#F5EDE8",
            lineHeight: 1.1,
          }}>
            {MAIN_TEXT}
          </div>
        </div>

        {/* 装飾ライン */}
        <div ref={decorLineRef} style={{
          width: 320,
          height: 1.5,
          background: "linear-gradient(90deg, #D4A8A0, rgba(212,168,160,0))",
          marginBottom: 20,
          transformOrigin: "left center",
        }} />

        {/* サブテキスト */}
        <div ref={subClipRef} style={{ overflow: "hidden" }}>
          <div ref={subTextRef} style={{
            fontSize: 30,
            fontWeight: 300,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            letterSpacing: "0.3em",
            color: "rgba(245,237,232,0.75)",
          }}>
            {SUB_TEXT}
          </div>
        </div>
      </AbsoluteFill>

      {/* Layer 5: スキャンライン（光の帯が走り抜ける） */}
      <div ref={scanLineRef} style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "18%",
        height: "100%",
        background: "linear-gradient(90deg, transparent 0%, rgba(255,220,210,0.12) 30%, rgba(255,230,220,0.55) 50%, rgba(255,220,210,0.12) 70%, transparent 100%)",
        boxShadow: "0 0 60px 20px rgba(255,200,180,0.3)",
        pointerEvents: "none",
      }} />
    </AbsoluteFill>
  );
};

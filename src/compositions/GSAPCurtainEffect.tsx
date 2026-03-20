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

export const GSAP_CURTAIN_DURATION = 120; // 4秒

const NUM_STRIPS = 8;       // 縦ストライプの数
const CURTAIN_START = 0;    // カーテン開始フレーム
const TEXT_START = 65;      // テキスト登場フレーム

const MAIN_TEXT = "艶やかな彩り";
const SUB_TEXT = "新作リップグロス";

export const GSAPCurtainEffect: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // タイミング（尺に合わせて比率で自動計算）
  const TEXT_START = Math.round(durationInFrames * 0.54);

  const stripRefs = useRef<(HTMLDivElement | null)[]>([]);
  const tlRef = useRef<gsap.core.Timeline | null>(null);
  const mainClipRef = useRef<HTMLDivElement>(null);
  const subClipRef = useRef<HTMLDivElement>(null);
  const mainTlRef = useRef<gsap.core.Timeline | null>(null);
  const subTlRef = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => {
    const strips = stripRefs.current.filter(Boolean) as HTMLDivElement[];
    if (strips.length === 0 || !mainClipRef.current || !subClipRef.current) return;

    // 各ストライプの初期状態
    strips.forEach((s) => {
      gsap.set(s, { scaleY: 1, transformOrigin: "top center" });
    });

    // カーテンタイムライン: ストライプが上から下へ消える（scaleY: 0）
    const tl = gsap.timeline({ paused: true });
    tl.to(strips, {
      scaleY: 0,
      duration: 1.4,
      ease: "power3.inOut",
      stagger: {
        each: 0.08,
        from: "start",
      },
    });
    tlRef.current = tl;

    // メインテキストリビール
    gsap.set(mainClipRef.current, { clipPath: "inset(0 100% 0 0)" });
    const mainTl = gsap.timeline({ paused: true });
    mainTl.to(mainClipRef.current, {
      clipPath: "inset(0 0% 0 0)",
      duration: 1.1,
      ease: "power3.inOut",
    });
    mainTlRef.current = mainTl;

    // サブテキストリビール
    gsap.set(subClipRef.current, { clipPath: "inset(0 100% 0 0)" });
    const subTl = gsap.timeline({ paused: true });
    subTl.to(subClipRef.current, {
      clipPath: "inset(0 0% 0 0)",
      duration: 0.9,
      ease: "power3.inOut",
    });
    subTlRef.current = subTl;
  }, []);

  useEffect(() => {
    const t = (f: number) => Math.max(0, (frame - f) / fps);
    tlRef.current?.seek(t(CURTAIN_START));
    mainTlRef.current?.seek(t(TEXT_START));
    subTlRef.current?.seek(t(TEXT_START + 18));
  }, [frame, fps]);

  // テキストのフェードイン補助
  const textOpacity = interpolate(frame, [TEXT_START, TEXT_START + 15], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      {/* Layer 1: 元動画（最初から表示、カーテンの下に） */}
      <OffthreadVideo
        src={staticFile("scene1_lipgloss.mp4")}
        style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover" }}
      />

      {/* Layer 2: 縦ストライプカーテン */}
      {Array.from({ length: NUM_STRIPS }).map((_, i) => (
        <div
          key={i}
          ref={(el) => { stripRefs.current[i] = el; }}
          style={{
            position: "absolute",
            top: 0,
            left: `${(i / NUM_STRIPS) * 100}%`,
            width: `${100 / NUM_STRIPS + 0.2}%`,
            height: "100%",
            background: i % 2 === 0
              ? "linear-gradient(180deg, rgb(148,98,97) 0%, rgb(175,128,126) 100%)"
              : "linear-gradient(180deg, rgb(168,115,114) 0%, rgb(195,148,146) 100%)",
            transformOrigin: "top center",
          }}
        />
      ))}

      {/* Layer 3: テキスト（カーテンが開いてから登場） */}
      <AbsoluteFill style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        paddingBottom: 170,
        paddingLeft: 80,
        opacity: textOpacity,
      }}>
        {/* メインテキスト */}
        <div ref={mainClipRef} style={{ overflow: "hidden", marginBottom: 18 }}>
          <div style={{
            fontSize: 80,
            fontWeight: 300,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            letterSpacing: "0.2em",
            color: "#F5EDE8",
            lineHeight: 1.1,
            textShadow: "0 2px 24px rgba(80,20,30,0.5)",
          }}>
            {MAIN_TEXT}
          </div>
        </div>

        {/* 細い区切りライン */}
        <div style={{
          width: 280,
          height: 1,
          background: "linear-gradient(90deg, rgba(212,168,160,0.9), rgba(212,168,160,0))",
          marginBottom: 18,
        }} />

        {/* サブテキスト */}
        <div ref={subClipRef} style={{ overflow: "hidden" }}>
          <div style={{
            fontSize: 30,
            fontWeight: 300,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            letterSpacing: "0.3em",
            color: "rgba(245,237,232,0.8)",
            textShadow: "0 2px 16px rgba(80,20,30,0.4)",
          }}>
            {SUB_TEXT}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

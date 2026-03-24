import React, { useEffect, useRef } from "react";
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { gsap } from "gsap";

// ===== シード付き乱数 =====
function seededRng(seed: number) {
  let s = seed >>> 0;
  return () => { s = (Math.imul(1664525, s) + 1013904223) >>> 0; return s / 4294967296; };
}

// ===== デフォルトアニメーション（全シーン共通） =====
const animC = (frame: number, text: string, startFrame = 20) => {
  const CHARS_DURATION = 30;
  const FADE_FRAMES = 40;
  const charsPerFrame = text.length / CHARS_DURATION;
  return text.split("").map((char, i) => {
    const charAppearFrame = startFrame + Math.floor(i / charsPerFrame);
    const age = frame - charAppearFrame;
    if (age < 0) return null;
    const t = Math.min(1, age / FADE_FRAMES);
    return (
      <span key={i} style={{ opacity: t, filter: `blur(${(1 - t) * 24}px)` }}>{char}</span>
    );
  });
};

// ===== T4: レンズフレア =====
const FLARE_X = 0.5;
const FLARE_Y = 0.38; // ゴールドリングの位置
const STREAKS = (() => {
  const rng = seededRng(99);
  return Array.from({ length: 12 }, (_, i) => ({
    angle: (i / 12) * Math.PI * 2,
    length: 0.15 + rng() * 0.25,
    width: 1 + rng() * 3,
    hue: rng() < 0.5 ? 35 + rng() * 20 : 45 + rng() * 15, // ゴールド系
  }));
})();
const GHOSTS = [
  { offset: 0.3, size: 0.04, hue: 45 },
  { offset: 0.55, size: 0.07, hue: 35 },
  { offset: 0.8, size: 0.03, hue: 50 },
  { offset: 1.1, size: 0.09, hue: 40 },
];

const LensFlareOverlay: React.FC<{ duration: number }> = ({ duration }) => {
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
    const flareIn = interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const flareOut = interpolate(frame, [duration - 15, duration], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const pulse = 0.75 + 0.25 * Math.sin(frame * 0.08);
    const alpha = flareIn * flareOut * pulse;

    // ブルーム
    [0.4, 0.12, 0.04].forEach((r, idx) => {
      const a = alpha * [0.15, 0.4, 0.85][idx];
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, width * r);
      grad.addColorStop(0, `rgba(255, 245, 220, ${a})`);
      grad.addColorStop(0.4, `rgba(255, 220, 180, ${a * 0.3})`);
      grad.addColorStop(1, `rgba(255, 220, 180, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, width * r, 0, Math.PI * 2);
      ctx.fill();
    });

    // 光の筋
    STREAKS.forEach((s) => {
      const diag = Math.sqrt(width * width + height * height);
      const ex = cx + Math.cos(s.angle) * diag * s.length;
      const ey = cy + Math.sin(s.angle) * diag * s.length;
      const grad = ctx.createLinearGradient(cx, cy, ex, ey);
      grad.addColorStop(0, `hsla(${s.hue}, 100%, 95%, ${alpha * 0.6})`);
      grad.addColorStop(0.3, `hsla(${s.hue}, 100%, 90%, ${alpha * 0.2})`);
      grad.addColorStop(1, `hsla(${s.hue}, 100%, 90%, 0)`);
      ctx.lineWidth = s.width;
      ctx.strokeStyle = grad;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(ex, ey);
      ctx.stroke();
    });

    // ゴースト
    const screenCx = width * 0.5;
    const screenCy = height * 0.5;
    GHOSTS.forEach((g) => {
      const gx = cx + (screenCx - cx) * g.offset * 2;
      const gy = cy + (screenCy - cy) * g.offset * 2;
      const r = width * g.size;
      const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, r);
      grad.addColorStop(0, `hsla(${g.hue}, 80%, 90%, ${alpha * 0.3})`);
      grad.addColorStop(1, `hsla(${g.hue}, 80%, 80%, 0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(gx, gy, r, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [frame, width, height, duration]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ position: "absolute", width: "100%", height: "100%" }}
    />
  );
};

// ===== T9: カーテンリビール =====
const NUM_STRIPS = 8;

const CurtainOverlay: React.FC<{ duration: number; textStartRatio?: number; textRender?: (frame: number) => React.ReactNode }> = ({ duration, textStartRatio = 0.5, textRender }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const stripRefs = useRef<(HTMLDivElement | null)[]>([]);
  const tlRef = useRef<gsap.core.Timeline | null>(null);
  const TEXT_START = Math.round(duration * textStartRatio);

  useEffect(() => {
    const strips = stripRefs.current.filter(Boolean) as HTMLDivElement[];
    if (strips.length === 0) return;
    strips.forEach((s) => gsap.set(s, { scaleY: 1, transformOrigin: "top center" }));
    const tl = gsap.timeline({ paused: true });
    tl.to(strips, {
      scaleY: 0,
      duration: 0.7,
      ease: "power3.inOut",
      stagger: { each: 0.04, from: "center" },
    });
    tlRef.current = tl;
  }, []);

  useEffect(() => {
    tlRef.current?.seek(Math.max(0, frame / fps));
  }, [frame, fps]);

  const textOpacity = interpolate(frame, [TEXT_START, TEXT_START + 15], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <>
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
              ? "linear-gradient(180deg, rgba(240,230,222,0.6) 0%, rgba(245,235,227,0.4) 100%)"
              : "linear-gradient(180deg, rgba(237,227,219,0.5) 0%, rgba(248,238,230,0.35) 100%)",
            backdropFilter: "blur(18px)",
            WebkitBackdropFilter: "blur(18px)",
            transformOrigin: "top center",
          }}
        />
      ))}
      {textRender && (
        <AbsoluteFill style={{ opacity: textOpacity }}>
          {textRender(Math.max(0, frame - TEXT_START))}
        </AbsoluteFill>
      )}
    </>
  );
};

// ===== GSAP スプリットテキスト =====
const SplitTextGSAP: React.FC<{
  text: string;
  startFrame?: number;
  style?: React.CSSProperties;
  vertical?: boolean;
}> = ({ text, startFrame = 5, style = {}, vertical = false }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const charRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const tlRef = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => {
    const chars = charRefs.current.filter(Boolean) as HTMLSpanElement[];
    if (chars.length === 0) return;
    chars.forEach((c) => gsap.set(c, { opacity: 0, y: 120, rotation: 25, scale: 0.3 }));
    const tl = gsap.timeline({ paused: true });
    tl.to(chars, {
      opacity: 1,
      y: 0,
      rotation: 0,
      scale: 1,
      duration: 1.5,
      ease: "power4.out",
      stagger: { each: 0.15, from: "start" },
    });
    tlRef.current = tl;
  }, []);

  useEffect(() => {
    const localTime = Math.max(0, (frame - startFrame) / fps);
    tlRef.current?.seek(localTime);
  }, [frame, fps, startFrame]);

  return (
    <div style={{
      display: "flex",
      flexDirection: vertical ? "column" : "row",
      flexWrap: "wrap",
      ...style,
    }}>
      {text.split("").map((char, i) => (
        <span
          key={i}
          ref={(el) => { charRefs.current[i] = el; }}
          style={{ display: "inline-block", willChange: "transform, opacity" }}
        >
          {char}
        </span>
      ))}
    </div>
  );
};

// ===== GSAP clipPathリビール =====
const ClipPathReveal: React.FC<{
  startFrame?: number;
  duration?: number;
  direction?: "left" | "right";
  children: React.ReactNode;
}> = ({ startFrame = 15, duration = 30, direction = "left", children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const containerRef = useRef<HTMLDivElement>(null);
  const tlRef = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const fromClip = direction === "left"
      ? "inset(0 100% 0 0)"
      : "inset(0 0 0 100%)";
    gsap.set(el, { clipPath: fromClip });
    const tl = gsap.timeline({ paused: true });
    tl.to(el, {
      clipPath: "inset(0 0% 0 0%)",
      duration: duration / fps,
      ease: "power3.inOut",
    });
    tlRef.current = tl;
  }, [direction, duration, fps]);

  useEffect(() => {
    const localTime = Math.max(0, (frame - startFrame) / fps);
    tlRef.current?.seek(localTime);
  }, [frame, fps, startFrame]);

  return (
    <div ref={containerRef} style={{ willChange: "clip-path" }}>
      {children}
    </div>
  );
};

// ===== T3: グリッター =====
type GlitterData = { x: number; y: number; vx: number; vy: number; size: number; rotation: number; rotSpeed: number; hue: number; delay: number; twinkle: number; };
const glitterData: GlitterData[] = (() => {
  const rng = seededRng(2024);
  return Array.from({ length: 140 }, () => ({
    x: rng(), y: -0.3 + rng() * 0.5,
    vx: (rng() - 0.5) * 0.001, vy: 0.001 + rng() * 0.002,
    size: 4 + rng() * 10,
    rotation: rng() * Math.PI * 2, rotSpeed: (rng() - 0.5) * 0.15,
    hue: 35 + rng() * 25, // ゴールド系のみ
    delay: Math.floor(rng() * 40),
    twinkle: 0.05 + rng() * 0.1,
  }));
})();

const GlitterOverlay: React.FC<{ duration: number }> = ({ duration }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, width, height);
    const globalAlpha = interpolate(frame, [0, 10, duration - 15, duration], [0, 1, 1, 0], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp",
    });

    glitterData.forEach((g) => {
      const f = frame - g.delay;
      if (f < 0) return;
      const px = (g.x + g.vx * f) * width;
      const py = (g.y + g.vy * f) * height;
      if (py > height + 20) return;
      const rot = g.rotation + g.rotSpeed * f;
      const twinkle = 0.5 + 0.5 * Math.sin(f * g.twinkle * Math.PI * 2);
      const alpha = globalAlpha * (0.4 + twinkle * 0.6);

      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(rot);
      ctx.globalAlpha = alpha;
      const grad = ctx.createLinearGradient(-g.size, 0, g.size, 0);
      grad.addColorStop(0, `hsla(${g.hue}, 100%, 95%, 0)`);
      grad.addColorStop(0.3, `hsla(${g.hue}, 100%, 90%, 1)`);
      grad.addColorStop(0.5, `hsla(${g.hue}, 60%, 100%, 1)`);
      grad.addColorStop(0.7, `hsla(${g.hue}, 100%, 90%, 1)`);
      grad.addColorStop(1, `hsla(${g.hue}, 100%, 95%, 0)`);
      ctx.beginPath();
      ctx.moveTo(0, -g.size * 0.35);
      ctx.lineTo(g.size, 0);
      ctx.lineTo(0, g.size * 0.35);
      ctx.lineTo(-g.size, 0);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.restore();
    });
  }, [frame, width, height, duration]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ position: "absolute", width: "100%", height: "100%" }}
    />
  );
};

// ===== クリップ定義 =====
const clips: {
  file: string;
  durationInFrames: number;
  render?: (frame: number) => React.ReactNode;
}[] = [
  // Scene 1 — フック（2秒）T4レンズフレア テロップなし
  {
    file: "scene1_フック_kling.mp4",
    durationInFrames: 60,
    render: () => <LensFlareOverlay duration={60} />,
  },
  // Scene 2 — 本題①（4秒）T9カーテンリビール + P4縦書き
  {
    file: "scene2_存在感_wan.mp4",
    durationInFrames: 120,
    render: (frame: number) => (
      <CurtainOverlay
        duration={120}
        textStartRatio={0.15}
        textRender={() => (
          <AbsoluteFill style={{
            justifyContent: "center",
            alignItems: "flex-end",
            paddingRight: 64,
          }}>
            <SplitTextGSAP
              text="肌に、静けさを。"
              startFrame={0}
              style={{
                writingMode: "vertical-rl" as const,
                fontSize: 72,
                fontWeight: 400,
                fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
                letterSpacing: "0.3em",
                lineHeight: 1,
                color: "#F5E6C8",
                textShadow: "0 1px 16px rgba(0,0,0,0.35)",
              }}
            />
          </AbsoluteFill>
        )}
      />
    ),
  },
  // Scene 3 — 本題②（3秒）P5左上ミニマル + clipPathリビール
  {
    file: "scene3_成分_kling.mp4",
    durationInFrames: 90,
    render: () => (
      <AbsoluteFill style={{
        justifyContent: "flex-start",
        alignItems: "flex-start",
        paddingTop: 200,
        paddingLeft: 56,
      }}>
        <ClipPathReveal startFrame={10} duration={25} direction="left">
          <div style={{
            fontSize: 52,
            fontWeight: 300,
            fontFamily: "Hiragino Sans, sans-serif",
            letterSpacing: "0.1em",
            lineHeight: 1.6,
            color: "#2A2A2A",
          }}>
            浸透型美容成分、凝縮。
          </div>
        </ClipPathReveal>
      </AbsoluteFill>
    ),
  },
  // Scene 4 — 本題③（3秒）テロップなし エフェクトなし
  {
    file: "scene4_使用シーン_kling.mp4",
    durationInFrames: 90,
  },
  // Scene 5 — CTA（3秒）T3グリッター + P2中央ブランドロゴ
  {
    file: "scene5_CTA_wan.mp4",
    durationInFrames: 90,
    render: (frame: number) => (
      <>
        <GlitterOverlay duration={90} />
        <AbsoluteFill style={{
          justifyContent: "flex-end",
          alignItems: "center",
          paddingBottom: 220,
        }}>
          <div style={{
            fontSize: 80,
            fontWeight: 200,
            fontFamily: "Hiragino Mincho ProN, YuMincho, serif",
            letterSpacing: "0.2em",
            color: "#FFFFFF",
          }}>
            {animC(frame, "今すぐチェック →", 10)}
          </div>
        </AbsoluteFill>
      </>
    ),
  },
];

// ===== Telopコンポーネント =====
const Telop: React.FC<(typeof clips)[number]> = (clip) => {
  const frame = useCurrentFrame();
  if (clip.render) return clip.render(frame);
  return null;
};

// ===== トランジション（白フラッシュ）=====
const FLASH_FRAMES = 6;
const WhiteFlash: React.FC = () => {
  const frame = useCurrentFrame();
  const transitions: number[] = [];
  let acc = 0;
  for (let i = 0; i < clips.length - 1; i++) {
    acc += clips[i].durationInFrames;
    transitions.push(acc);
  }
  const opacity = transitions.reduce((o, t) => {
    const dist = Math.abs(frame - t);
    if (dist > FLASH_FRAMES) return o;
    return Math.max(o, interpolate(dist, [0, FLASH_FRAMES], [0.6, 0], { extrapolateRight: "clamp" }));
  }, 0);
  if (opacity === 0) return null;
  return <AbsoluteFill style={{ backgroundColor: `rgba(255,255,255,${opacity})`, zIndex: 10 }} />;
};

// ===== メインコンポーネント =====
export const AdVideo: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Audio src={staticFile("bgm.mp3")} volume={0.3} />
      <Sequence from={15}>
        <Audio src={staticFile("narration.wav")} volume={0.7} />
      </Sequence>
      {clips.map((clip, idx) => {
        const start = from;
        from += clip.durationInFrames;
        return (
          <Sequence key={idx} from={start} durationInFrames={clip.durationInFrames}>
            <AbsoluteFill>
              <OffthreadVideo
                src={staticFile(clip.file)}
                style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center center" }}
              />
              <Telop {...clip} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
      <WhiteFlash />
    </AbsoluteFill>
  );
};

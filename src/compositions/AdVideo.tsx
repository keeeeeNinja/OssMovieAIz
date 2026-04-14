import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";

const FPS = 30;
const GAP = 0;

type Visual =
  | { type: "video"; file: string }
  | { type: "videos"; files: string[] }
  | { type: "image"; file: string }
  | { type: "images"; files: string[]; splitEvenly: true; zoomFiles?: string[] };

type Scene = {
  id: string;
  narration: string;
  durationSec: number;
  visual: Visual;
  zoom?: boolean;
  subtitles: string[];
  command?: string;
};

const scenes: Scene[] = [
  { id: "S01", narration: "narration_S01.wav", durationSec: 8.32,
    visual: { type: "videos", files: ["scene_S01_wan21.mp4", "scene_S01b_wan21.mp4"] },
    subtitles: ["コードを書けない人でも\nパソコンに日本語で話しかけるだけで作業ができる", "それがClaude Codeです"] },
  { id: "S02", narration: "narration_S02.wav", durationSec: 10.92,
    visual: { type: "videos", files: ["scene_S02a_wan21.mp4", "scene_S02b_wan21.mp4", "scene_S02c_wan21.mp4"] },
    subtitles: ["Claude Codeは Anthropic社が作った公式ツールです", "ターミナル上で動き あなたの代わりに\nファイルを読んだり 書いたり 作ったりしてくれます"] },
  { id: "S03", narration: "narration_S03.wav", durationSec: 7.64,
    visual: { type: "videos", files: ["scene_S03_wan21.mp4", "scene_S03b_wan21.mp4"] },
    subtitles: ["WindowsでもMacでも まっさらな環境から\nClaude Codeを使えるようにする動画です"] },
  { id: "S04", narration: "narration_S04.wav", durationSec: 11.92,
    visual: { type: "videos", files: ["scene_S04a_wan21.mp4", "scene_S04b_wan21.mp4", "scene_S04c_wan21.mp4"] },
    subtitles: ["必要なものは Node.js  Claudeのアカウント\nターミナル の3つ", "Windowsの方は Git Bashという\nツールを追加で入れます"] },
  { id: "S05", narration: "narration_S05.wav", durationSec: 9.72,
    visual: { type: "images", files: ["mac_spotlight.png", "mac_terminal.png"], splitEvenly: true },
    subtitles: ["⌘+SpaceでSpotlightを開き\n「ターミナル」と入力してEnter", "ターミナルが起動すれば準備完了です"] },
  { id: "S06", narration: "narration_S06.wav", durationSec: 16.48,
    visual: { type: "images", files: ["win_gitscm.png", "win_gitbash.png"], splitEvenly: true, zoomFiles: ["win_gitbash.png"] },
    subtitles: ["ブラウザで git-scm.com を開き\nダウンロードから実行ファイルを取得", "全てNextを押せばインストール完了\nスタートメニューからGit Bashを起動"] },
  { id: "S07", narration: "narration_S07.wav", durationSec: 16.68,
    visual: { type: "images", files: ["mac_nodejs_page.png", "mac_nodejs_installer.png"], splitEvenly: true },
    subtitles: ["nodejs.org のダウンロードページを開き\nOSを macOS に切り替え", "緑のmacOSインストーラーボタンから\npkgをダウンロード ダブルクリックで実行"] },
  { id: "S08", narration: "narration_S08.wav", durationSec: 15.64,
    visual: { type: "image", file: "win_nodejs.png" },
    subtitles: ["同じページでOSをWindowsに切り替え", "緑のWindowsインストーラーボタンから\nmsiをダウンロード 全てNextで完了"] },
  { id: "S09", narration: "narration_S09.wav", durationSec: 10.96,
    visual: { type: "images", files: ["mac_node_v.png", "win_node_npm.png"], splitEvenly: true }, zoom: true,
    subtitles: ["ターミナルで node -v と打ってEnter", "バージョン番号が出れば\nインストール成功です"],
    command: "node -v" },
  { id: "S10", narration: "narration_S10.wav", durationSec: 8.32,
    visual: { type: "image", file: "win_node_npm.png" }, zoom: true,
    subtitles: ["このコマンドをターミナルに貼り付けてEnter"],
    command: "npm install -g @anthropic-ai/claude-code" },
  { id: "S11", narration: "narration_S11.wav", durationSec: 9.64,
    visual: { type: "image", file: "win_mkdir_cd.png" }, zoom: true,
    subtitles: ["3つのコマンドでデスクトップに\n新しいフォルダを作り そこに移動"],
    command: "mkdir -p ~/Desktop/my-project\ncd ~/Desktop/my-project\npwd" },
  { id: "S12", narration: "narration_S12.wav", durationSec: 6.20,
    visual: { type: "videos", files: ["scene_S12_wan21.mp4", "scene_S12b_wan21.mp4"] },
    subtitles: ["claude と打ってEnter\nClaude Codeが起動します"],
    command: "claude" },
  { id: "S13", narration: "narration_S13.wav", durationSec: 19.12,
    visual: { type: "images", files: ["win_claude_theme.png", "win_claude_security.png", "win_claude_login_method.png", "win_trust_folder.png"], splitEvenly: true }, zoom: true,
    subtitles: ["テーマはデフォルトのままEnter", "セキュリティの注意書きを確認してEnter", "Claude Account with Subscription を選択", "Yes, I trust this folder を選択"] },
  { id: "S14", narration: "narration_S14.wav", durationSec: 12.56,
    visual: { type: "images", files: ["win_auth_approve.png", "win_auth_success.png", "win_login_success.png"], splitEvenly: true }, zoom: true,
    subtitles: ["ブラウザが自動で開きます", "承認するボタンを押す", "ターミナルに戻ってEnterを押す"] },
  { id: "S15", narration: "narration_S15.wav", durationSec: 6.72,
    visual: { type: "videos", files: ["scene_S15_wan21.mp4", "scene_S15b_wan21.mp4"] },
    subtitles: ["日本語でClaudeに話しかけてみましょう\n返事が返ってきたら成功です"] },
  { id: "S16", narration: "narration_S16.wav", durationSec: 12.44,
    visual: { type: "images", files: ["win_init_fail.png", "win_readme_create.png"], splitEvenly: true }, zoom: true,
    subtitles: ["日本語でお願いすれば\nファイルを作ってくれます", "README.mdを作ってもらいましょう\n一瞬で完成！"] },
  { id: "S17", narration: "narration_S17.wav", durationSec: 16.88,
    visual: { type: "images", files: ["win_init_success.png", "win_explorer.png"], splitEvenly: true }, zoom: true,
    subtitles: ["/init と打ってEnter", "CLAUDE.mdがあると 次回以降\nプロジェクトの内容を覚えた状態で作業できます"],
    command: "/init" },
  { id: "S18", narration: "narration_S18.wav", durationSec: 4.56,
    visual: { type: "video", file: "scene_S18_wan21.mp4" },
    subtitles: ["Claude Codeの導入は完了です\nお疲れさまでした"] },
  { id: "S19", narration: "narration_S19.wav", durationSec: 15.96,
    visual: { type: "images", files: ["win_cursor_error.png", "win_cursor_error_explain.png", "win_cursor_fix.png"], splitEvenly: true }, zoom: true,
    subtitles: ["CursorやVS Codeの統合ターミナルで\n権限エラーが出ることがあります", "画面のコマンドを実行してください", "もう一度 claude と打てば起動できます"] },
];

const bgmTracks = [
  { file: "bgm_1.mp3", startScene: "S01" },
  { file: "bgm_2.mp3", startScene: "S05" },
  { file: "bgm_3.mp3", startScene: "S12" },
  { file: "bgm_4.mp3", startScene: "S16" },
];

function getFrames(s: Scene): number {
  return Math.round(s.durationSec * FPS) + GAP;
}

const SceneImage: React.FC<{ file: string; totalFrames: number; zoom?: boolean }> = ({ file, totalFrames, zoom }) => {
  const frame = useCurrentFrame();
  const scale = zoom
    ? interpolate(frame, [0, totalFrames], [0.92, 0.98], { extrapolateRight: "clamp" })
    : interpolate(frame, [0, totalFrames], [1, 1.05], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ backgroundColor: "#111", justifyContent: "center", alignItems: "center", overflow: "hidden" }}>
      <Img
        src={staticFile(file)}
        style={zoom ? {
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
        } : {
          maxWidth: "95%",
          maxHeight: "90%",
          objectFit: "contain",
          borderRadius: 12,
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

const CLIP_DURATION = 5.0625;

const SceneVideo: React.FC<{ file: string; totalFrames: number }> = ({ file, totalFrames }) => {
  const sceneDuration = totalFrames / FPS;
  const playbackRate = CLIP_DURATION / sceneDuration;
  return (
    <OffthreadVideo
      src={staticFile(file)}
      playbackRate={playbackRate}
      style={{ width: "100%", height: "100%", objectFit: "contain" }}
    />
  );
};

const SceneMultiVideo: React.FC<{ files: string[]; totalFrames: number }> = ({ files, totalFrames }) => {
  const frame = useCurrentFrame();
  const perClip = Math.floor(totalFrames / files.length);
  const idx = Math.min(Math.floor(frame / perClip), files.length - 1);

  return (
    <AbsoluteFill style={{ backgroundColor: "#111" }}>
      {files.map((file, i) => {
        const clipStart = i * perClip;
        const clipEnd = i === files.length - 1 ? totalFrames : (i + 1) * perClip;
        const clipDuration = clipEnd - clipStart;
        const clipDurationSec = clipDuration / FPS;
        const playbackRate = CLIP_DURATION / clipDurationSec;

        if (frame < clipStart || frame >= clipEnd) return null;

        return (
          <Sequence key={file} from={clipStart} durationInFrames={clipDuration}>
            <OffthreadVideo
              src={staticFile(file)}
              playbackRate={playbackRate}
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const SceneMultiImage: React.FC<{ files: string[]; totalFrames: number; zoom?: boolean; zoomFiles?: string[] }> = ({ files, totalFrames, zoom, zoomFiles }) => {
  const frame = useCurrentFrame();
  const perImage = Math.floor(totalFrames / files.length);
  const idx = Math.min(Math.floor(frame / perImage), files.length - 1);
  const localFrame = frame - idx * perImage;
  const isZoom = zoom || (zoomFiles?.includes(files[idx]) ?? false);

  const fadeIn = interpolate(localFrame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const scale = isZoom
    ? interpolate(localFrame, [0, perImage], [0.92, 0.98], { extrapolateRight: "clamp" })
    : interpolate(localFrame, [0, perImage], [1, 1.05], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: "#111", justifyContent: "center", alignItems: "center", overflow: "hidden" }}>
      <Img
        src={staticFile(files[idx])}
        style={isZoom ? {
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: fadeIn,
          transform: `scale(${scale})`,
        } : {
          maxWidth: "95%",
          maxHeight: "90%",
          objectFit: "contain",
          borderRadius: 12,
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
          opacity: fadeIn,
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};

const SceneVisual: React.FC<{ visual: Visual; totalFrames: number; zoom?: boolean }> = ({ visual, totalFrames, zoom }) => {
  if (visual.type === "video") return <SceneVideo file={visual.file} totalFrames={totalFrames} />;
  if (visual.type === "videos") return <SceneMultiVideo files={visual.files} totalFrames={totalFrames} />;
  if (visual.type === "image") return <SceneImage file={visual.file} totalFrames={totalFrames} zoom={zoom} />;
  return <SceneMultiImage files={visual.files} totalFrames={totalFrames} zoom={zoom} zoomFiles={visual.zoomFiles} />;
};

const SceneSubtitle: React.FC<{ subtitles: string[]; totalFrames: number }> = ({ subtitles, totalFrames }) => {
  const frame = useCurrentFrame();
  const perSub = Math.floor(totalFrames / subtitles.length);
  const idx = Math.min(Math.floor(frame / perSub), subtitles.length - 1);
  const localFrame = frame - idx * perSub;
  const fadeIn = interpolate(localFrame, [0, 8], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 60,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0,0,0,0.75)",
          color: "#fff",
          fontSize: 32,
          fontFamily: '"Noto Sans JP", sans-serif',
          fontWeight: 700,
          padding: "12px 32px",
          borderRadius: 10,
          textAlign: "center",
          lineHeight: 1.5,
          whiteSpace: "pre-line",
          maxWidth: "85%",
        }}
      >
        {subtitles[idx]}
      </div>
    </div>
  );
};

const SceneCommand: React.FC<{ command: string; totalFrames: number }> = ({ command, totalFrames }) => {
  const frame = useCurrentFrame();
  const slideIn = interpolate(frame, [0, 15], [30, 0], { extrapolateRight: "clamp" });
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        top: 100,
        left: 0,
        right: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        opacity,
        transform: `translateY(${slideIn}px)`,
      }}
    >
      <div
        style={{
          color: "#fff",
          fontSize: 20,
          fontFamily: '"Noto Sans JP", sans-serif',
          fontWeight: 700,
          marginBottom: 8,
          backgroundColor: "rgba(74,158,255,0.85)",
          padding: "4px 16px",
          borderRadius: 6,
        }}
      >
        ターミナルに入力
      </div>
      <div
        style={{
          backgroundColor: "rgba(30,30,30,0.95)",
          border: "2px solid #4a9eff",
          color: "#4ae34a",
          fontSize: 38,
          fontFamily: '"SF Mono", "Fira Code", "Consolas", monospace',
          fontWeight: 600,
          padding: "18px 44px",
          borderRadius: 12,
          whiteSpace: "pre-line",
          lineHeight: 1.6,
          boxShadow: "0 4px 24px rgba(74,158,255,0.3)",
        }}
      >
        {command}
      </div>
      <div
        style={{
          color: "rgba(255,255,255,0.7)",
          fontSize: 16,
          fontFamily: '"Noto Sans JP", sans-serif',
          marginTop: 8,
          textAlign: "center",
          lineHeight: 1.6,
        }}
      >
        {command.includes("\n") && "※ 1行ずつ入力してください\n"}
        ※ コマンドは概要欄からコピーできます
      </div>
    </div>
  );
};

const SceneLabel: React.FC<{ id: string }> = ({ id }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10, 40, 50], [0, 0.7, 0.7, 0], { extrapolateRight: "clamp" });
  if (opacity <= 0) return null;

  const isSupp = id === "S19";
  const label = isSupp ? "補足" : id.replace("S0", "S").replace("S", "");

  return (
    <div
      style={{
        position: "absolute",
        top: 60,
        left: 40,
        backgroundColor: "rgba(0,0,0,0.6)",
        color: "#fff",
        fontSize: 28,
        fontFamily: '"Noto Sans JP", sans-serif',
        fontWeight: 700,
        padding: "6px 18px",
        borderRadius: 8,
        opacity,
      }}
    >
      {isSupp ? "補足" : `Step ${label}`}
    </div>
  );
};

const FADE_OUT_FRAMES = 45; // 1.5秒

const FadeOut: React.FC<{ totalFrames: number }> = ({ totalFrames }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [totalFrames - FADE_OUT_FRAMES, totalFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  if (opacity <= 0) return null;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000", opacity }} />
  );
};

export const AdVideo: React.FC = () => {
  const sceneFrames = scenes.map(getFrames);
  const totalFrames = sceneFrames.reduce((a, b) => a + b, 0);

  const sceneStarts: number[] = [];
  let acc = 0;
  for (const f of sceneFrames) {
    sceneStarts.push(acc);
    acc += f;
  }

  const bgmStartFrames = bgmTracks.map((t) => {
    const idx = scenes.findIndex((s) => s.id === t.startScene);
    return { file: t.file, from: sceneStarts[idx] };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#111" }}>
      {bgmStartFrames.map((b) => (
        <Sequence key={b.file} from={b.from}>
          <Audio src={staticFile(b.file)} volume={0.25} />
        </Sequence>
      ))}

      {scenes.map((scene, i) => (
        <Sequence key={scene.id} from={sceneStarts[i]} durationInFrames={sceneFrames[i]}>
          <AbsoluteFill>
            <SceneVisual visual={scene.visual} totalFrames={sceneFrames[i]} zoom={scene.zoom} />
            <Audio src={staticFile(scene.narration)} volume={0.4} />
            {scene.command && <SceneCommand command={scene.command} totalFrames={sceneFrames[i]} />}
            <SceneSubtitle subtitles={scene.subtitles} totalFrames={sceneFrames[i]} />
            <SceneLabel id={scene.id} />
          </AbsoluteFill>
        </Sequence>
      ))}

      <FadeOut totalFrames={totalFrames} />
    </AbsoluteFill>
  );
};

export const tutorialTotalFrames = scenes.map(getFrames).reduce((a, b) => a + b, 0);

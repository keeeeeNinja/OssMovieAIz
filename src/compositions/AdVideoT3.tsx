import React from "react";
import { AdVideoBase, animC, Clip, telopBase, wrapperBase } from "./shared";

// ===== Theme3 テロップ文言（まつ毛は"自信"だった / 価値観・気づき系） =====
const C1_TEXT = "まつ毛は\n\"自信\"だった";
const C3_TEXT = "人の目を見られなかった私\n写真にも写りたくなかった";
const C4_TEXT = "毎晩30秒の習慣で\nまつ毛が変わったら\n顔を上げられるようになった";
const C5_TEXT = "自信は自分で\n作るものだった";
const C6_TEXT = "保存して自信を育てよう♡\nフォローもよろしく!";

const clips: Clip[] = [
  {
    file: "scene_T3_C01_wan21.mp4",
    durationInFrames: 75,
    render: (frame) => (
      <div style={wrapperBase(0.78)}>
        <div style={telopBase(180, 7)}>{animC(frame, C1_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T3_C03_wan21.mp4",
    durationInFrames: 117,
    render: (frame) => (
      <div style={wrapperBase(0.85)}>
        <div style={telopBase(72, 4)}>{animC(frame, C3_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T3_C04_wan21.mp4",
    durationInFrames: 100,
    render: (frame) => (
      <div style={wrapperBase(0.85)}>
        <div style={telopBase(82, 5)}>{animC(frame, C4_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T3_C05_wan21.mp4",
    durationInFrames: 88,
    render: (frame) => (
      <div style={wrapperBase(0.82)}>
        <div style={telopBase(108, 5)}>{animC(frame, C5_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T3_C06_wan21.mp4",
    durationInFrames: 27,
    render: (frame) => (
      <div style={wrapperBase(0.1)}>
        <div style={telopBase(62, 4)}>{animC(frame, C6_TEXT, 0)}</div>
      </div>
    ),
  },
];

export const AdVideoT3: React.FC = () => (
  <AdVideoBase clips={clips} narration="narration_t3.wav" bgm="bgm_t3.mp3" />
);

export const adVideoT3Clips = clips;

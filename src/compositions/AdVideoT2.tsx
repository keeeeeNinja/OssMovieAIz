import React from "react";
import { AdVideoBase, animC, Clip, telopBase, wrapperBase } from "./shared";

// ===== Theme2 テロップ文言（お金かけたのに変わらなかった話 / ストーリー系） =====
const C1_TEXT = "お金かけたのに\n変わらなかった話";
const C3_TEXT = "3年間でコスメに30万円…\nでも何も変わらなかった";
const C4_TEXT = "そんな私がたった1本で\n2週間で目元が別人に";
const C5_TEXT = "遠回りの3年間が\nウソみたい";
const C6_TEXT = "保存して後悔しないケアを♡\nフォローもよろしく!";

const clips: Clip[] = [
  {
    file: "scene_T2_C01_wan21.mp4",
    durationInFrames: 75,
    render: (frame) => (
      <div style={wrapperBase(0.78)}>
        <div style={telopBase(120, 5)}>{animC(frame, C1_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T2_C03_wan21.mp4",
    durationInFrames: 117,
    render: (frame) => (
      <div style={wrapperBase(0.85)}>
        <div style={telopBase(72, 4)}>{animC(frame, C3_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T2_C04_wan21.mp4",
    durationInFrames: 100,
    render: (frame) => (
      <div style={wrapperBase(0.85)}>
        <div style={telopBase(86, 5)}>{animC(frame, C4_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T2_C05_wan21.mp4",
    durationInFrames: 88,
    render: (frame) => (
      <div style={wrapperBase(0.82)}>
        <div style={telopBase(110, 5)}>{animC(frame, C5_TEXT, 3)}</div>
      </div>
    ),
  },
  {
    file: "scene_T2_C06_wan21.mp4",
    durationInFrames: 27,
    render: (frame) => (
      <div style={wrapperBase(0.1)}>
        <div style={telopBase(62, 4)}>{animC(frame, C6_TEXT, 0)}</div>
      </div>
    ),
  },
];

export const AdVideoT2: React.FC = () => (
  <AdVideoBase clips={clips} narration="narration_t2.wav" bgm="bgm_t2.mp3" />
);

export const adVideoT2Clips = clips;

import React from "react";
import { AdVideoBase, Clip } from "./shared";

// bs_composition.json から telop-baseline / telop-design がここを上書きする
const clips: Clip[] = [];

export const AdVideo: React.FC = () => (
  <AdVideoBase clips={clips} />
);

export const adVideoClips = clips;
export const adVideoTotalFrames = clips.reduce((s, c) => s + c.durationInFrames, 0) || 30;

import React from "react";
import { Composition } from "remotion";
import { AdVideo, adVideoTotalFrames } from "./compositions/AdVideo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AdVideo"
        component={AdVideo}
        durationInFrames={adVideoTotalFrames}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};

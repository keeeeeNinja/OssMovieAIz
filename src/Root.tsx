import React from "react";
import { Composition } from "remotion";
import { AdVideo, tutorialTotalFrames } from "./compositions/AdVideo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AdVideo"
        component={AdVideo}
        durationInFrames={tutorialTotalFrames}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};

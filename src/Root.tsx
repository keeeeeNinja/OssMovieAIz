import { Composition } from "remotion";
import { AdVideo } from "./compositions/AdVideo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AdVideo"
        component={AdVideo}
        durationInFrames={1820}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};

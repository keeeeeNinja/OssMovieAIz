import React from "react";
import { Composition } from "remotion";
import { AdVideo } from "./compositions/AdVideo";
import { ParticleBottle, PARTICLE_BOTTLE_DURATION } from "./compositions/ParticleBottle";
import { GlitterEffect, GLITTER_DURATION } from "./compositions/GlitterEffect";
import { LensFlareEffect, LENS_FLARE_DURATION } from "./compositions/LensFlareEffect";
import { LipParticleEffect, LIP_PARTICLE_DURATION } from "./compositions/LipParticleEffect";
import { ChromaticEffect, CHROMATIC_DURATION } from "./compositions/ChromaticEffect";
import { ParticleEffect } from "./compositions/ParticleEffect";
import { Particle3DEffect, PARTICLE_3D_DURATION } from "./compositions/Particle3DEffect";
import { GSAPLineEffect, GSAP_LINE_DURATION } from "./compositions/GSAPLineEffect";
import { GSAPMaskRevealEffect, GSAP_MASK_REVEAL_DURATION } from "./compositions/GSAPMaskRevealEffect";
import { GSAPCurtainEffect, GSAP_CURTAIN_DURATION } from "./compositions/GSAPCurtainEffect";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AdVideo"
        component={AdVideo}
        durationInFrames={765}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="ParticleBottle"
        component={ParticleBottle}
        durationInFrames={PARTICLE_BOTTLE_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="GlitterEffect"
        component={GlitterEffect}
        durationInFrames={GLITTER_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="GSAPLineEffect"
        component={GSAPLineEffect}
        durationInFrames={GSAP_LINE_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="Particle3DEffect"
        component={Particle3DEffect}
        durationInFrames={PARTICLE_3D_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="LipParticleEffect"
        component={LipParticleEffect}
        durationInFrames={LIP_PARTICLE_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="LensFlareEffect"
        component={LensFlareEffect}
        durationInFrames={LENS_FLARE_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="GSAPMaskRevealEffect"
        component={GSAPMaskRevealEffect}
        durationInFrames={GSAP_MASK_REVEAL_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="GSAPCurtainEffect"
        component={GSAPCurtainEffect}
        durationInFrames={GSAP_CURTAIN_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="ChromaticEffect"
        component={ChromaticEffect}
        durationInFrames={CHROMATIC_DURATION}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="ParticleEffect"
        component={ParticleEffect}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};

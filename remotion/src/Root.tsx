import React from 'react';
import {CalculateMetadataFunction, Composition, Still} from 'remotion';
import {DEMO_MAIN, DEMO_THUMB} from './demo';
import {Main} from './Main';
import {Thumbnail} from './Thumbnail';
import type {MainProps, ThumbnailProps} from './types';

// Size and length come from the props, so one composition renders every video, Short and style.
const metadata: CalculateMetadataFunction<MainProps> = ({props}) => ({
  durationInFrames: Math.max(1, props.durationInFrames),
  fps: props.fps,
  width: props.width,
  height: props.height,
});

export const Root: React.FC = () => (
  <>
    <Composition
      id="Main"
      component={Main}
      defaultProps={DEMO_MAIN}
      calculateMetadata={metadata}
      durationInFrames={DEMO_MAIN.durationInFrames}
      fps={30}
      width={1920}
      height={1080}
    />
    <Composition
      id="Short"
      component={Main}
      defaultProps={{...DEMO_MAIN, layout: 'vertical', width: 1080, height: 1920}}
      calculateMetadata={metadata}
      durationInFrames={DEMO_MAIN.durationInFrames}
      fps={30}
      width={1080}
      height={1920}
    />
    <Still id="Thumbnail" component={Thumbnail} defaultProps={DEMO_THUMB as ThumbnailProps} width={1280} height={720} />
  </>
);

import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, Loop, OffthreadVideo, useCurrentFrame} from 'remotion';
import {asset} from './asset';
import {fontStack} from './fonts';
import {MockupScene} from './MockupScene';
import type {Brand, MainProps, Segment as Seg} from './types';

// Entering animation for one segment, over `t` frames from its first frame.
const enterStyle = (kind: string | undefined, frame: number, t: number): React.CSSProperties => {
  if (!kind || kind === 'none') return {};
  const p = interpolate(frame, [0, t], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  switch (kind) {
    case 'crossfade':
    case 'dip-to-black':
      return {opacity: p};
    case 'slide':
    case 'number-wipe':
      return {transform: `translateX(${(1 - p) * 100}%)`};
    case 'whip': {
      const q = interpolate(frame, [0, Math.max(2, t * 0.6)], [0, 1], {extrapolateRight: 'clamp'});
      return {transform: `translateX(${(1 - q) * 100}%)`, filter: `blur(${(1 - q) * 24}px)`};
    }
    default:
      return {opacity: p};
  }
};

const Card: React.FC<{text: string; brand: Brand; vertical: boolean}> = ({text, brand, vertical}) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(circle at 30% 30%, ${brand.primary ?? '#FFD400'}33, ${brand.secondary ?? '#111'} 70%)`,
      justifyContent: 'center',
      alignItems: 'center',
      padding: vertical ? 80 : 160,
    }}
  >
    <div
      style={{
        fontFamily: fontStack(brand.font_heading),
        fontWeight: 900,
        fontSize: vertical ? 96 : 110,
        lineHeight: 1.1,
        color: brand.text ?? '#fff',
        textAlign: 'center',
        textTransform: 'uppercase',
      }}
    >
      {text}
    </div>
  </AbsoluteFill>
);

export const SegmentView: React.FC<{seg: Seg; props: MainProps}> = ({seg, props}) => {
  const frame = useCurrentFrame(); // relative to the segment's Sequence
  const vertical = props.layout === 'vertical';
  const fit: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    objectPosition: `${props.cropX * 100}% 50%`,
  };
  let kb: React.CSSProperties = {};
  if (seg.kenBurns && seg.kenBurns > 1) {
    const s = interpolate(frame, [0, seg.dur], [1, seg.kenBurns]);
    const dir = seg.index % 2 === 0 ? 1 : -1;
    const x = interpolate(frame, [0, seg.dur], [0, dir * 2]);
    kb = {transform: `scale(${s}) translateX(${x}%)`};
  }

  let body: React.ReactNode = null;
  if (seg.kind === 'video' && seg.src) {
    const video = (
      <OffthreadVideo src={asset(seg.src, props.assetBase)} trimBefore={seg.trimBefore ?? 0} muted={seg.muted} style={fit} />
    );
    body = seg.loopFrames ? <Loop durationInFrames={seg.loopFrames}>{video}</Loop> : video;
  } else if (seg.kind === 'image' && seg.src) {
    body = <Img src={asset(seg.src, props.assetBase)} style={fit} />;
  } else if (seg.kind === 'mockup' && seg.mockupId) {
    body = <MockupScene id={seg.mockupId} label={seg.text ?? ''} />;
  } else {
    body = <Card text={seg.text ?? ''} brand={props.brand} vertical={vertical} />;
  }

  return (
    <AbsoluteFill style={{overflow: 'hidden', ...enterStyle(seg.enter, frame, props.transitionFrames)}}>
      <AbsoluteFill style={kb}>{body}</AbsoluteFill>
    </AbsoluteFill>
  );
};

import React from 'react';
import {AbsoluteFill, Audio, interpolate, random, Sequence, useCurrentFrame} from 'remotion';
import {asset} from './asset';
import {Captions} from './Captions';
import {Overlays} from './Overlays';
import {SegmentView} from './Segment';
import type {Caption, MainProps, Zoom} from './types';

const GRADES: Record<string, string> = {
  neutral: 'none',
  contrast: 'contrast(1.12) saturate(1.05)',
  vivid: 'saturate(1.3) contrast(1.08)',
  film: 'contrast(1.05) saturate(0.85) sepia(0.12)',
  warm: 'sepia(0.18) saturate(1.1)',
  moody: 'contrast(1.15) saturate(0.8) brightness(0.92)',
  'teal-orange': 'contrast(1.1) saturate(1.15) hue-rotate(-8deg)',
};

const zoomAt = (zooms: Zoom[], frame: number): React.CSSProperties => {
  const z = zooms.find((w) => frame >= w.from && frame < w.from + w.dur);
  if (!z) return {};
  let tx = 0;
  let ty = 0;
  if (z.shake) {
    const k = interpolate(frame - z.from, [0, 8], [1, 0], {extrapolateRight: 'clamp'});
    tx = (random(`x${frame}`) - 0.5) * 18 * k;
    ty = (random(`y${frame}`) - 0.5) * 18 * k;
  }
  return {transform: `scale(${z.scale}) translate(${tx}px, ${ty}px)`};
};

// Music sits lower while someone is talking and comes up in the gaps.
const speaking = (caps: Caption[], frame: number) => caps.some((c) => frame >= c.from - 6 && frame < c.to + 6);

export const Main: React.FC<MainProps> = (props) => {
  const frame = useCurrentFrame();
  const music = props.music;
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{filter: GRADES[props.grade] ?? 'none'}}>
        <AbsoluteFill style={zoomAt(props.zooms, frame)}>
          {props.segments.map((s, i) => (
            <Sequence key={i} from={s.from} durationInFrames={s.dur} name={`${s.kind} ${s.index}`}>
              <SegmentView seg={s} props={props} />
            </Sequence>
          ))}
        </AbsoluteFill>
      </AbsoluteFill>
      <Overlays props={props} />
      <Captions props={props} />
      {props.audio.map((a, i) => (
        <Sequence key={`a${i}`} from={a.from} layout="none">
          <Audio src={asset(a.src, props.assetBase)} volume={a.volume} />
        </Sequence>
      ))}
      {music ? (
        <Audio
          src={asset(music.src, props.assetBase)}
          loop
          volume={(f) => (music.duck && !speaking(props.captions, f) ? Math.min(0.35, music.volume * 1.8) : music.volume)}
        />
      ) : null}
      {props.sfx.map((s, i) => (
        <Sequence key={`s${i}`} from={s.from} durationInFrames={45} layout="none">
          <Audio src={asset(s.src, props.assetBase)} volume={s.volume} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

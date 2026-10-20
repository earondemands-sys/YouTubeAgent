import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontStack} from './fonts';
import type {Caption, MainProps} from './types';

const outline = (px: number): React.CSSProperties => ({
  WebkitTextStroke: `${px}px #000`,
  paintOrder: 'stroke fill',
  textShadow: `0 ${px}px ${px * 2}px rgba(0,0,0,0.55)`,
});

// Binary search: the caption on screen at `frame`, if any.
const at = (caps: Caption[], frame: number): Caption | null => {
  let lo = 0;
  let hi = caps.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (caps[mid].to <= frame) lo = mid + 1;
    else if (caps[mid].from > frame) hi = mid - 1;
    else return caps[mid];
  }
  return null;
};

export const Captions: React.FC<{props: MainProps}> = ({props}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const c = props.style.captions;
  if (c.mode === 'none') return null;
  const cap = at(props.captions, frame);
  if (!cap) return null;

  const vertical = props.layout === 'vertical';
  const fontSize = Math.round(c.size * (vertical ? width * 1.25 : height));
  const hi = props.brand.primary ?? '#FFD400';
  const base = props.brand.text ?? '#FFFFFF';
  const top = vertical ? (c.position === 'center' ? '58%' : '70%') : c.position === 'center' ? '50%' : '84%';
  const pop = spring({frame: frame - cap.from, fps, config: {damping: 14, stiffness: 220}, durationInFrames: 8});

  const words = cap.words.map((w, i) => {
    const active = frame >= w.from && frame < Math.max(w.to, w.from + 2);
    const spoken = frame >= w.from;
    let color = base;
    let scale = 1;
    if (c.mode === 'word-pop' && c.highlight && active) {
      color = hi;
      scale = interpolate(frame - w.from, [0, 3, 6], [1, 1.18, 1.08], {extrapolateRight: 'clamp'});
    } else if (c.mode === 'karaoke') {
      color = spoken ? hi : base;
    } else if (c.mode === 'line' && c.highlight && active) {
      color = hi;
    }
    return (
      <span
        key={i}
        style={{
          display: 'inline-block',
          margin: `0 ${fontSize * 0.14}px`,
          color,
          transform: `scale(${scale})`,
          // word-pop shows words as they are said; the others show the whole line
          opacity: c.mode === 'word-pop' ? (spoken ? 1 : 0) : 1,
        }}
      >
        {c.uppercase ? w.w.toUpperCase() : w.w}
      </span>
    );
  });

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top,
          left: '6%',
          right: '6%',
          transform: `translateY(-50%) scale(${c.mode === 'line' ? 1 : 0.92 + 0.08 * pop})`,
          textAlign: 'center',
          fontFamily: fontStack(props.brand.font_heading),
          fontWeight: 900,
          fontSize,
          lineHeight: 1.15,
          ...outline(Math.max(3, Math.round(fontSize * 0.07))),
        }}
      >
        {words}
      </div>
    </AbsoluteFill>
  );
};

import React from 'react';
import {AbsoluteFill, Img} from 'remotion';
import {asset} from './asset';
import {fontStack} from './fonts';
import {ThumbnailHeadlineChips} from './ThumbnailHeadlineChips';
import type {ThumbnailProps} from './types';

// Abstract "dashboard" blocks (a header bar, a ticket list, a chart) - never a real product UI.
const Backdrop: React.FC<{side: 'left' | 'right'; opacity: number; tint: string}> = ({side, opacity, tint}) => {
  const card: React.CSSProperties = {position: 'absolute', borderRadius: 18, background: 'rgba(255,255,255,0.9)'};
  const row = (top: number, w: number, accent?: boolean): React.CSSProperties => ({
    ...card,
    left: 40,
    top,
    width: w,
    height: 34,
    borderRadius: 10,
    background: accent ? tint : 'rgba(255,255,255,0.75)',
  });
  return (
    <div
      style={{
        position: 'absolute',
        top: 40,
        [side]: 30,
        width: 760,
        height: 560,
        opacity,
        filter: 'blur(5px)',
        transform: `perspective(1400px) rotateY(${side === 'left' ? 14 : -14}deg) rotateX(4deg)`,
      }}
    >
      <div style={{...card, inset: 0, background: 'rgba(255,255,255,0.18)', border: '3px solid rgba(255,255,255,0.6)'}} />
      <div style={{...card, left: 0, right: 0, top: 0, height: 70, borderRadius: '18px 18px 0 0'}} />
      <div style={row(110, 420, true)} />
      <div style={row(170, 560)} />
      <div style={row(230, 500)} />
      <div style={row(290, 600)} />
      <div style={row(350, 460)} />
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          style={{...card, left: 60 + i * 70, bottom: 30, width: 46, height: 40 + ((i * 37) % 5) * 22, borderRadius: 6}}
        />
      ))}
      <div style={{...card, right: 40, bottom: 30, width: 260, height: 150, background: tint}} />
    </div>
  );
};

// 1280x720 (render with --scale for larger). The bottom-right corner stays clear: YouTube draws the duration there.
export const Thumbnail: React.FC<ThumbnailProps> = (props) =>
  props.layout === 'headline-chips' ? <ThumbnailHeadlineChips {...props} /> : <WordsThumbnail {...props} />;

// face-right / face-left / no-face: up to three big words, optional badge.
const WordsThumbnail: React.FC<ThumbnailProps> = ({
  background,
  face,
  text,
  layout,
  brand,
  textColor,
  highlightWord,
  oneLine,
  badge,
  badgeColor,
  badgeTextColor,
  bgColor,
  glowColor,
  backdrop,
  backdropOpacity,
  faceHeight,
  faceTop,
  faceInset,
  assetBase,
}) => {
  const words = text.trim().split(/\s+/).slice(0, 3);
  const hasFace = Boolean(face) && layout !== 'no-face';
  const faceLeft = layout === 'face-left';
  const textSide = faceLeft ? 'right' : 'left';
  const faceSide = faceLeft ? 'left' : 'right';
  const longest = oneLine ? words.join(' ').length : Math.max(...words.map((w) => w.length), 1);
  // fit the longest line into the text column
  const column = hasFace ? (oneLine ? 700 : 580) : 1120;
  const fontSize = Math.min(hasFace ? 190 : 230, Math.floor(column / (longest * 0.62)));
  const hi = highlightWord ?? words.length - 1;
  const base = bgColor ?? brand.secondary ?? '#111';
  const heading = fontStack(brand.font_heading);
  const wordStyle = (i: number): React.CSSProperties => ({
    color: i === hi ? brand.primary ?? '#FFD400' : textColor ?? brand.text ?? '#fff',
    WebkitTextStroke: `${Math.round(fontSize * 0.06)}px #000`,
    paintOrder: 'stroke fill',
    textShadow: '0 8px 24px rgba(0,0,0,0.6)',
  });

  return (
    <AbsoluteFill style={{backgroundColor: base}}>
      {background ? (
        <Img src={asset(background, assetBase)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      ) : (
        <AbsoluteFill
          style={{
            background: bgColor
              ? `radial-gradient(ellipse 120% 90% at 30% 40%, ${base} 0%, ${base} 55%, rgba(0,0,0,0.55) 100%)`
              : `linear-gradient(135deg, ${base} 0%, ${base} 45%, ${brand.primary ?? '#FFD400'} 140%)`,
          }}
        />
      )}
      {backdrop === 'ui' ? (
        <Backdrop side={textSide} opacity={backdropOpacity ?? 0.18} tint={glowColor ?? brand.primary ?? '#FFD400'} />
      ) : null}
      {glowColor && hasFace ? (
        <div
          style={{
            position: 'absolute',
            top: '8%',
            [faceSide]: -120,
            width: 820,
            height: 820,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${glowColor} 0%, transparent 65%)`,
            opacity: 0.55,
          }}
        />
      ) : null}
      {/* darken the text side so the words hold contrast at feed size */}
      <AbsoluteFill
        style={{
          background: `linear-gradient(${faceLeft ? 270 : 90}deg, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.35) 55%, rgba(0,0,0,0) 80%)`,
        }}
      />
      {hasFace ? (
        <Img
          src={asset(face as string, assetBase)}
          style={{
            position: 'absolute',
            ...(faceTop !== undefined ? {top: `${faceTop}%`} : {bottom: 0}),
            height: `${faceHeight ?? 96}%`,
            [faceSide]: faceInset ?? 20,
            filter: 'drop-shadow(0 0 18px rgba(0,0,0,0.85)) drop-shadow(0 0 4px #fff)',
          }}
        />
      ) : null}
      <div
        style={{
          position: 'absolute',
          top: 0,
          bottom: 90,
          [textSide]: 60,
          width: column,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: faceLeft ? 'flex-end' : 'flex-start',
          fontFamily: heading,
          fontWeight: 900,
          fontSize,
          lineHeight: 0.98,
          textTransform: 'uppercase',
          textAlign: faceLeft ? 'right' : 'left',
        }}
      >
        {oneLine ? (
          <div style={{whiteSpace: 'nowrap'}}>
            {words.map((w, i) => (
              <span key={i} style={wordStyle(i)}>
                {i ? ' ' : ''}
                {w}
              </span>
            ))}
          </div>
        ) : (
          words.map((w, i) => (
            <div key={i} style={wordStyle(i)}>
              {w}
            </div>
          ))
        )}
        {badge ? (
          <div
            style={{
              marginTop: Math.round(fontSize * 0.28),
              padding: '6px 34px 14px',
              borderRadius: 22,
              background: badgeColor ?? brand.primary ?? '#FFD400',
              color: badgeTextColor ?? '#000',
              border: '5px solid #000',
              boxShadow: '0 10px 30px rgba(0,0,0,0.55)',
              fontSize: Math.round(fontSize * 0.68),
              fontWeight: 800,
              lineHeight: 1.25,
              textTransform: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {badge}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

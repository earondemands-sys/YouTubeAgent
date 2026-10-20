import React from 'react';
import {AbsoluteFill, Img} from 'remotion';
import {asset} from './asset';
import {fontStack} from './fonts';
import type {ThumbnailProps} from './types';

// 1280x720. The bottom-right corner stays clear: YouTube draws the duration there.
export const Thumbnail: React.FC<ThumbnailProps> = ({background, face, text, layout, brand, textColor, highlightWord, assetBase}) => {
  const words = text.trim().split(/\s+/).slice(0, 3);
  const hasFace = Boolean(face) && layout !== 'no-face';
  const faceLeft = layout === 'face-left';
  const longest = Math.max(...words.map((w) => w.length), 1);
  // fit the longest word into the text column
  const column = hasFace ? 580 : 1120;
  const fontSize = Math.min(hasFace ? 190 : 230, Math.floor(column / (longest * 0.62)));
  const hi = highlightWord ?? words.length - 1;

  return (
    <AbsoluteFill style={{backgroundColor: brand.secondary ?? '#111'}}>
      {background ? (
        <Img src={asset(background, assetBase)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      ) : (
        <AbsoluteFill
          style={{
            background: `linear-gradient(135deg, ${brand.secondary ?? '#111'} 0%, ${brand.secondary ?? '#111'} 45%, ${
              brand.primary ?? '#FFD400'
            } 140%)`,
          }}
        />
      )}
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
            bottom: 0,
            height: '96%',
            [faceLeft ? 'left' : 'right']: 20,
            filter: 'drop-shadow(0 0 18px rgba(0,0,0,0.85)) drop-shadow(0 0 4px #fff)',
          }}
        />
      ) : null}
      <div
        style={{
          position: 'absolute',
          top: 0,
          bottom: 90,
          [faceLeft ? 'right' : 'left']: 60,
          width: column,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          fontFamily: fontStack(brand.font_heading),
          fontWeight: 900,
          fontSize,
          lineHeight: 0.98,
          textTransform: 'uppercase',
          textAlign: faceLeft ? 'right' : 'left',
        }}
      >
        {words.map((w, i) => (
          <div
            key={i}
            style={{
              color: i === hi ? brand.primary ?? '#FFD400' : textColor ?? brand.text ?? '#fff',
              WebkitTextStroke: `${Math.round(fontSize * 0.06)}px #000`,
              paintOrder: 'stroke fill',
              textShadow: '0 8px 24px rgba(0,0,0,0.6)',
            }}
          >
            {w}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

import React from 'react';
import {AbsoluteFill, Img} from 'remotion';
import {asset} from './asset';
import {fontStack} from './fonts';
import type {HeadlinePart, ThumbIcon, ThumbnailProps} from './types';

// 'headline-chips': kicker pill, one headline line, a tilted highlight box, a chip row (+ ticket
// card), small module tags, presenter on the right. All words come from props. 1280x720 design
// space; the bottom-right corner stays clear for YouTube's duration badge.

const Icon: React.FC<{kind?: ThumbIcon; size: number; color: string; stroke?: number}> = ({kind, size, color, stroke}) => {
  if (!kind || kind === 'none') return null;
  const sw = stroke ?? 3.2;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{flex: 'none', display: 'block'}}>
      {kind === 'code' ? (
        <g fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
          <polyline points="8.5,6 2.5,12 8.5,18" />
          <polyline points="15.5,6 21.5,12 15.5,18" />
        </g>
      ) : (
        <polyline points="4,12.5 9.5,18 20,6.5" fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
      )}
    </svg>
  );
};

export const ThumbnailHeadlineChips: React.FC<ThumbnailProps> = ({
  background,
  face,
  text,
  brand,
  textColor,
  bgColor,
  bgEdge,
  glowColor,
  faceHeight,
  faceTop,
  faceInset,
  kicker,
  headline,
  highlight,
  chips,
  card,
  tags,
  headingFont,
  headlineSize,
  highlightSize,
  rays,
  assetBase,
}) => {
  const font = fontStack(headingFont ?? brand.font_heading);
  const body = fontStack(brand.font_body);
  const yellow = brand.primary ?? '#FFD400';
  const white = textColor ?? brand.text ?? '#FFFFFF';
  const base = bgColor ?? '#21463F';
  const glow = glowColor ?? '#357560';
  const edge = bgEdge ?? '#172C32';
  const parts: HeadlinePart[] = headline ?? text.trim().split(/\s+/).map((w) => ({text: w}));
  const hSize = headlineSize ?? 142;
  const bSize = highlightSize ?? 172;
  const chipShadow = '0 8px 18px rgba(0,0,0,0.45)';

  return (
    <AbsoluteFill style={{backgroundColor: base, overflow: 'hidden'}}>
      {background ? (
        <Img src={asset(background, assetBase)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      ) : (
        <>
          <AbsoluteFill
            style={{
              background: `linear-gradient(100deg, ${edge} 0%, ${base} 48%, ${glow} 100%)`,
            }}
          />
          <AbsoluteFill
            style={{background: `radial-gradient(ellipse 45% 70% at 86% 42%, ${glow} 0%, transparent 100%)`, opacity: 0.8}}
          />
          {rays !== false ? (
            <AbsoluteFill
              style={{
                background:
                  'repeating-conic-gradient(from 0deg at 80% 42%, rgba(255,255,255,0.055) 0deg 6deg, rgba(255,255,255,0) 6deg 16deg)',
                WebkitMaskImage: 'radial-gradient(ellipse 75% 95% at 80% 42%, #000 0%, rgba(0,0,0,0.55) 45%, transparent 85%)',
              }}
            />
          ) : null}
          <AbsoluteFill style={{boxShadow: 'inset 0 0 120px rgba(0,0,0,0.28)'}} />
        </>
      )}

      {face ? (
        <Img
          src={asset(face, assetBase)}
          style={{
            position: 'absolute',
            ...(faceTop !== undefined ? {top: `${faceTop}%`} : {bottom: 0}),
            height: `${faceHeight ?? 104}%`,
            right: faceInset ?? 0,
            filter:
              'drop-shadow(0 0 2.5px #fff) drop-shadow(0 0 2.5px #fff) drop-shadow(0 0 1.5px #fff) drop-shadow(0 0 1px #fff) drop-shadow(0 18px 30px rgba(0,0,0,0.55))',
          }}
        />
      ) : null}

      {kicker && kicker.length ? (
        <div
          style={{
            position: 'absolute',
            left: 52,
            top: 40,
            height: 54,
            padding: '0 8px 0 24px',
            borderRadius: 27,
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            boxShadow: '0 6px 16px rgba(0,0,0,0.35)',
            whiteSpace: 'nowrap',
          }}
        >
          {kicker.map((k, i) =>
            k.kind === 'wordmark' ? (
              <span key={i} style={{fontFamily: font, fontWeight: 600, fontSize: 34, letterSpacing: -0.6, color: k.color ?? '#14211F', lineHeight: 1, marginTop: -3}}>
                {k.text}
              </span>
            ) : k.kind === 'highlight' ? (
              <span
                key={i}
                style={{
                  fontFamily: font,
                  fontWeight: 800,
                  fontSize: 22,
                  lineHeight: 1,
                  color: k.color ?? '#111',
                  background: yellow,
                  borderRadius: 20,
                  padding: '9px 16px 11px',
                }}
              >
                {k.text}
              </span>
            ) : (
              <span
                key={i}
                style={{fontFamily: font, fontWeight: 700, fontSize: 19, letterSpacing: 1.6, color: k.color ?? '#33413E', lineHeight: 1, paddingRight: 16}}
              >
                {k.text}
              </span>
            ),
          )}
        </div>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: 48,
          top: 132,
          fontFamily: font,
          fontWeight: 800,
          fontSize: hSize,
          lineHeight: 1,
          letterSpacing: -hSize * 0.035,
          whiteSpace: 'nowrap',
          textShadow: '0 8px 22px rgba(0,0,0,0.55)',
        }}
      >
        {parts.map((p, i) => (
          <span key={i} style={{color: p.color ?? white}}>
            {i ? ' ' : ''}
            {p.text}
          </span>
        ))}
      </div>

      {highlight ? (
        <div
          style={{
            position: 'absolute',
            left: 46,
            top: 288,
            transform: `rotate(${highlight.rotate ?? -3}deg)`,
            transformOrigin: 'left center',
            padding: `${Math.round(bSize * 0.04)}px ${Math.round(bSize * 0.17)}px ${Math.round(bSize * 0.1)}px`,
            borderRadius: 22,
            background: `linear-gradient(100deg, ${highlight.color ?? yellow} 0%, ${highlight.colorTo ?? '#F4B323'} 100%)`,
            boxShadow: '12px 14px 0 rgba(4,18,15,0.75), 0 22px 40px rgba(0,0,0,0.45)',
            fontFamily: font,
            fontWeight: 800,
            fontSize: bSize,
            lineHeight: 1.08,
            letterSpacing: -bSize * 0.035,
            color: highlight.textColor ?? '#0E1412',
            whiteSpace: 'nowrap',
          }}
        >
          {highlight.text}
        </div>
      ) : null}

      {chips?.length || card ? (
        <div style={{position: 'absolute', left: 56, top: 532, display: 'flex', alignItems: 'center', gap: 18}}>
          {(chips ?? []).map((c, i) => (
            <div
              key={i}
              style={{
                height: 70,
                padding: '0 24px 0 20px',
                borderRadius: 14,
                background: c.color,
                border: '4px solid rgba(255,255,255,0.92)',
                boxShadow: chipShadow,
                transform: `rotate(${c.rotate ?? 0}deg)`,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                fontFamily: font,
                fontWeight: 700,
                fontSize: 38,
                letterSpacing: -0.8,
                color: c.textColor ?? '#fff',
                whiteSpace: 'nowrap',
              }}
            >
              <Icon kind={c.icon} size={34} color={c.textColor ?? '#fff'} />
              <span style={{marginTop: 3}}>{c.text}</span>
            </div>
          ))}
          {card ? (
            <div
              style={{
                marginLeft: 18,
                height: 66,
                padding: '0 22px 0 14px',
                borderRadius: 12,
                background: '#fff',
                boxShadow: chipShadow,
                transform: `rotate(${card.rotate ?? -3}deg)`,
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                whiteSpace: 'nowrap',
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 9,
                  background: card.iconColor ?? '#3DAF78',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon kind={card.icon ?? 'check'} size={28} color="#fff" />
              </div>
              <div style={{display: 'flex', flexDirection: 'column', gap: 3}}>
                <span style={{fontFamily: body, fontWeight: 700, fontSize: 16, letterSpacing: 0.6, color: '#5B6664', lineHeight: 1}}>
                  {card.title}
                </span>
                <span style={{fontFamily: font, fontWeight: 800, fontSize: 21, color: '#141B19', lineHeight: 1}}>{card.subtitle}</span>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {tags?.length ? (
        <div style={{position: 'absolute', left: 58, top: 646, display: 'flex', alignItems: 'center', gap: 12}}>
          {tags.map((t, i) => (
            <div
              key={i}
              style={{
                height: 38,
                padding: '0 14px',
                borderRadius: 9,
                background: t.color,
                display: 'flex',
                alignItems: 'center',
                fontFamily: font,
                fontWeight: 700,
                fontSize: 20,
                letterSpacing: 0.3,
                color: t.textColor ?? '#fff',
                boxShadow: '0 4px 10px rgba(0,0,0,0.35)',
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{marginTop: 2}}>{t.text}</span>
            </div>
          ))}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

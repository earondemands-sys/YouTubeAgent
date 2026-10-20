import {useAudioData, visualizeAudio} from '@remotion/media-utils';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {asset} from './asset';
import {fontStack} from './fonts';
import type {Brand, MainProps, Overlay} from './types';

type P = {o: Overlay; brand: Brand; vertical: boolean};

const fadeInOut = (frame: number, dur: number, edge = 8) =>
  interpolate(frame, [0, edge, Math.max(edge + 1, dur - edge), dur], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

const ProgressBar: React.FC<P> = ({o, brand}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          height: 8,
          width: `${(frame / o.dur) * 100}%`,
          background: brand.primary ?? '#FFD400',
        }}
      />
    </AbsoluteFill>
  );
};

const Letterbox: React.FC<P> = () => {
  const {width, height} = useVideoConfig();
  const bar = Math.max(0, (height - width / 2.39) / 2);
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: bar, background: '#000'}} />
      <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: bar, background: '#000'}} />
    </AbsoluteFill>
  );
};

const Waveform: React.FC<P> = ({o, brand}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const data = useAudioData(asset(o.src as string, o.base as string | undefined));
  if (!data) return null;
  const bars = visualizeAudio({fps, frame, audioData: data, numberOfSamples: 64});
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 40}}>
      <div style={{display: 'flex', alignItems: 'flex-end', gap: 6, height: 120, width: width * 0.5}}>
        {bars.map((v, i) => (
          <div key={i} style={{flex: 1, height: `${Math.min(100, 8 + v * 260)}%`, background: brand.primary, borderRadius: 4}} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

const LowerThird: React.FC<P> = ({o, brand, vertical}) => {
  const frame = useCurrentFrame();
  const x = interpolate(frame, [0, 12, o.dur - 12, o.dur], [-110, 0, 0, -110], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', left: vertical ? 40 : 80, bottom: vertical ? 420 : 140, transform: `translateX(${x}%)`}}>
        <div
          style={{
            background: brand.primary,
            color: brand.secondary,
            fontFamily: fontStack(brand.font_heading),
            fontWeight: 900,
            fontSize: 46,
            padding: '10px 26px',
          }}
        >
          {o.title as string}
        </div>
        {o.subtitle ? (
          <div
            style={{
              background: brand.secondary,
              color: brand.text,
              fontFamily: fontStack(brand.font_body),
              fontWeight: 600,
              fontSize: 30,
              padding: '8px 26px',
              display: 'inline-block',
            }}
          >
            {o.subtitle as string}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

const CenterCard: React.FC<P & {big?: boolean; dim?: boolean}> = ({o, brand, vertical, big, dim}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 13}, durationInFrames: 12});
  return (
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
        background: dim ? `rgba(0,0,0,${0.55 * fadeInOut(frame, o.dur)})` : undefined,
        opacity: fadeInOut(frame, o.dur),
      }}
    >
      <div
        style={{
          transform: `scale(${0.85 + 0.15 * s})`,
          fontFamily: fontStack(brand.font_heading),
          fontWeight: 900,
          fontSize: big ? (vertical ? 110 : 120) : vertical ? 72 : 80,
          color: brand.text,
          textAlign: 'center',
          textTransform: 'uppercase',
          padding: '18px 40px',
          maxWidth: '86%',
          lineHeight: 1.08,
          borderBottom: `10px solid ${brand.primary}`,
          WebkitTextStroke: '3px #000',
          paintOrder: 'stroke fill',
        }}
      >
        {(o.title ?? o.text) as string}
      </div>
    </AbsoluteFill>
  );
};

const TextSlam: React.FC<P> = ({o, brand, vertical}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 5, 9], [2.4, 0.95, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.quad)});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', opacity: fadeInOut(frame, o.dur, 4)}}>
      <div
        style={{
          transform: `scale(${scale}) rotate(-3deg)`,
          background: brand.primary,
          color: brand.secondary,
          fontFamily: fontStack(brand.font_heading),
          fontWeight: 900,
          fontSize: vertical ? 92 : 110,
          padding: '6px 34px',
          textTransform: 'uppercase',
        }}
      >
        {o.text as string}
      </div>
    </AbsoluteFill>
  );
};

const Step: React.FC<P> = ({o, brand, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 14}, durationInFrames: 12});
  const all = (o.all as string[]) ?? [];
  const n = o.n as number;
  const showList = Boolean(o.checklist) && frame < fps * 3.5;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: vertical ? 220 : 50,
          left: vertical ? 40 : 60,
          transform: `translateX(${(1 - s) * -120}%)`,
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          fontFamily: fontStack(brand.font_heading),
        }}
      >
        <div style={{background: brand.primary, color: brand.secondary, fontWeight: 900, fontSize: 38, padding: '8px 18px'}}>
          STEP {n}/{o.of as number}
        </div>
        <div style={{color: brand.text, fontWeight: 800, fontSize: 36, WebkitTextStroke: '2px #000', paintOrder: 'stroke fill'}}>
          {o.title as string}
        </div>
      </div>
      {showList ? (
        <div
          style={{
            position: 'absolute',
            right: 60,
            top: vertical ? 400 : 150,
            background: 'rgba(0,0,0,0.72)',
            padding: '24px 32px',
            borderLeft: `8px solid ${brand.primary}`,
            fontFamily: fontStack(brand.font_body),
            fontSize: 30,
            color: brand.text,
            opacity: fadeInOut(frame, fps * 3.5),
          }}
        >
          {all.map((t, i) => (
            <div key={i} style={{opacity: i + 1 <= n ? 1 : 0.45, margin: '6px 0'}}>
              {i + 1 < n ? '✓' : i + 1 === n ? '▶' : '○'} {t || `Step ${i + 1}`}
            </div>
          ))}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const ListItem: React.FC<P> = ({o, brand, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = frame < fps * 2;
  const s = spring({frame, fps, config: {damping: 12}, durationInFrames: 14});
  return (
    <AbsoluteFill>
      {intro ? (
        <AbsoluteFill
          style={{justifyContent: 'center', alignItems: 'center', opacity: fadeInOut(frame, fps * 2, 5), background: 'rgba(0,0,0,0.78)'}}
        >
          <div style={{transform: `scale(${0.6 + 0.4 * s})`, textAlign: 'center', fontFamily: fontStack(brand.font_heading)}}>
            <div style={{fontSize: vertical ? 260 : 300, fontWeight: 900, color: brand.primary, lineHeight: 1, WebkitTextStroke: '6px #000', paintOrder: 'stroke fill'}}>
              #{o.n as number}
            </div>
            <div style={{fontSize: 64, fontWeight: 900, color: brand.text, textTransform: 'uppercase', WebkitTextStroke: '3px #000', paintOrder: 'stroke fill'}}>
              {o.title as string}
            </div>
          </div>
        </AbsoluteFill>
      ) : o.badge ? (
        <div
          style={{
            position: 'absolute',
            top: vertical ? 220 : 50,
            left: vertical ? 40 : 60,
            width: 110,
            height: 110,
            borderRadius: 55,
            background: brand.primary,
            color: brand.secondary,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            fontFamily: fontStack(brand.font_heading),
            fontWeight: 900,
            fontSize: 54,
          }}
        >
          {o.n as number}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const Callout: React.FC<P> = ({o, brand, vertical}) => {
  const frame = useCurrentFrame();
  const code = o.variant === 'code-highlight' || o.variant === 'keyboard-shortcut';
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: vertical ? 300 : 70,
          right: vertical ? 40 : 70,
          maxWidth: vertical ? '80%' : '42%',
          opacity: fadeInOut(frame, o.dur),
          background: code ? '#0d1117' : 'rgba(0,0,0,0.78)',
          border: `4px solid ${brand.primary}`,
          borderRadius: code ? 10 : 0,
          padding: '18px 26px',
          color: code ? '#7ee787' : brand.text,
          fontFamily: code ? 'Menlo, Monaco, monospace' : fontStack(brand.font_body),
          fontWeight: code ? 600 : 800,
          fontSize: 38,
        }}
      >
        {o.text as string}
      </div>
    </AbsoluteFill>
  );
};

const Hook: React.FC<P> = ({o, brand}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 12}, durationInFrames: 10});
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          marginTop: 260,
          maxWidth: '88%',
          transform: `scale(${0.7 + 0.3 * s})`,
          opacity: fadeInOut(frame, o.dur, 4),
          background: brand.primary,
          color: brand.secondary,
          fontFamily: fontStack(brand.font_heading),
          fontWeight: 900,
          fontSize: 78,
          lineHeight: 1.08,
          textAlign: 'center',
          textTransform: 'uppercase',
          padding: '18px 30px',
        }}
      >
        {o.text as string}
      </div>
    </AbsoluteFill>
  );
};

const VIEWS: Record<string, React.FC<P>> = {
  'progress-bar': ProgressBar,
  letterbox: Letterbox,
  waveform: Waveform,
  'lower-third': LowerThird,
  'title-card': (p) => <CenterCard {...p} big dim />,
  'chapter-card': (p) => <CenterCard {...p} dim />,
  step: Step,
  list: ListItem,
  'text-slam': TextSlam,
  callout: Callout,
  hook: Hook,
};

export const Overlays: React.FC<{props: MainProps}> = ({props}) => {
  const vertical = props.layout === 'vertical';
  const list: Overlay[] = [...props.overlays];
  for (const o of list) if (o.type === 'waveform') o.base = props.assetBase;
  if (props.hook) list.push({type: 'hook', from: props.hook.from, dur: props.hook.dur, text: props.hook.text});
  return (
    <>
      {list.map((o, i) => {
        const View = VIEWS[o.type];
        if (!View || o.dur <= 0) return null;
        return (
          <Sequence key={i} from={o.from} durationInFrames={o.dur} name={o.type} layout="none">
            <View o={o} brand={props.brand} vertical={vertical} />
          </Sequence>
        );
      })}
    </>
  );
};

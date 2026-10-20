import type {MainProps, ThumbnailProps} from './types';

// What Remotion Studio shows with no project loaded: a card, captions and a few overlays.
const brand = {primary: '#FFD400', secondary: '#111111', accent: '#FF3B30', text: '#FFFFFF', font_heading: 'Montserrat', font_body: 'Inter'};

export const DEMO_MAIN: MainProps = {
  fps: 30,
  width: 1920,
  height: 1080,
  durationInFrames: 150,
  layout: 'landscape',
  cropX: 0.5,
  frameRange: null,
  mode: 'faceless',
  styleId: 'hormozi',
  style: {
    id: 'hormozi',
    name: 'Hormozi Captions',
    captions: {mode: 'word-pop', position: 'center', size: 0.075, max_words: 3, highlight: true, uppercase: true},
    zoom: {punch_in_every: 5, scale: 1.15},
    cuts: {jump_cuts: true, transition: 'none'},
    overlays: [],
    grade: 'contrast',
  },
  brand,
  segments: [{kind: 'card', text: 'YouTube Agent', from: 0, dur: 150, index: 0}],
  audio: [],
  music: null,
  sfx: [],
  captions: [
    {from: 10, to: 60, words: [{w: 'Fifteen', from: 10, to: 25}, {w: 'agents', from: 25, to: 40}, {w: 'ready', from: 40, to: 60}]},
    {from: 70, to: 140, words: [{w: 'Let', from: 70, to: 85}, {w: 'us', from: 85, to: 95}, {w: 'go', from: 95, to: 140}]},
  ],
  zooms: [{from: 75, dur: 75, scale: 1.1}],
  overlays: [{type: 'progress-bar', from: 0, dur: 150}],
  hook: null,
  transitionFrames: 10,
  grade: 'contrast',
};

export const DEMO_THUMB: ThumbnailProps = {background: null, face: null, text: 'AGENTS DO IT', layout: 'no-face', brand};

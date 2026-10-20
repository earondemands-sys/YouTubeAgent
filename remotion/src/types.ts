// The shape scripts/render_props.py writes. Frames everywhere unless a name says otherwise.

export type Brand = {
  primary?: string;
  secondary?: string;
  accent?: string;
  text?: string;
  font_heading?: string;
  font_body?: string;
};

export type Style = {
  id: string;
  name: string;
  captions: {
    mode: 'none' | 'line' | 'word-pop' | 'karaoke';
    position: 'bottom' | 'center';
    size: number;
    max_words: number;
    highlight: boolean;
    uppercase?: boolean;
    speaker_label?: boolean;
  };
  zoom: {punch_in_every?: number; scale?: number; ken_burns?: boolean; shake?: boolean};
  cuts: {jump_cuts: boolean; transition: string};
  overlays: string[];
  grade?: string;
};

export type Segment = {
  kind: 'video' | 'image' | 'card';
  src?: string;
  text?: string;
  from: number;
  dur: number;
  trimBefore?: number;
  muted?: boolean;
  index: number;
  enter?: string;
  kenBurns?: number;
  loopFrames?: number;
};

export type Word = {w: string; from: number; to: number};
export type Caption = {from: number; to: number; words: Word[]};
export type Zoom = {from: number; dur: number; scale: number; shake?: boolean};

export type Overlay = {
  type: string;
  from: number;
  dur: number;
  [key: string]: unknown;
};

export type MainProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  layout: 'landscape' | 'vertical';
  cropX: number;
  frameRange: [number, number] | null;
  mode: 'recorded' | 'faceless';
  styleId: string;
  style: Style;
  brand: Brand;
  segments: Segment[];
  audio: {src: string; from: number; volume: number}[];
  music: {src: string; volume: number; duck: boolean} | null;
  sfx: {from: number; src: string; volume: number}[];
  captions: Caption[];
  zooms: Zoom[];
  overlays: Overlay[];
  hook: {text: string; from: number; dur: number} | null;
  transitionFrames: number;
  grade: string;
  warnings?: string[];
  assetBase?: string;
};

export type ThumbnailProps = {
  background: string | null;
  face: string | null;
  text: string;
  layout: 'face-right' | 'face-left' | 'no-face';
  brand: Brand;
  textColor?: string;
  highlightWord?: number;
  assetBase?: string;
};

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
  kind: 'video' | 'image' | 'card' | 'mockup';
  src?: string;
  text?: string;
  // A project can opt into an original, vector-only instructional mockup timeline.
  // This is intentionally a scene identifier rather than an image or a captured UI.
  mockupId?: number;
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

// --- 'headline-chips' layout: kicker pill, headline line, tilted highlight box, chip row, tags ---
export type ThumbIcon = 'code' | 'check' | 'none';
export type KickerPart = {text: string; kind?: 'wordmark' | 'caps' | 'highlight'; color?: string};
export type HeadlinePart = {text: string; color?: string};
export type ThumbHighlight = {text: string; color?: string; colorTo?: string; textColor?: string; rotate?: number};
export type ThumbChip = {text: string; color: string; textColor?: string; icon?: ThumbIcon; rotate?: number};
export type ThumbCard = {title: string; subtitle: string; icon?: ThumbIcon; iconColor?: string; rotate?: number};
export type ThumbTag = {text: string; color: string; textColor?: string};

export type ThumbnailProps = {
  background: string | null;
  face: string | null;
  text: string;
  layout: 'face-right' | 'face-left' | 'no-face' | 'headline-chips';
  brand: Brand;
  textColor?: string;
  highlightWord?: number;
  // all optional; leaving them out gives the original look
  oneLine?: boolean; // the words on one line instead of stacked
  badge?: string; // a short label pill under the words (any script; fontStack covers Telugu)
  badgeColor?: string; // pill fill, default brand.primary
  badgeTextColor?: string; // default #000
  bgColor?: string; // solid base colour for the gradient background, default brand.secondary
  glowColor?: string; // soft radial glow behind the face
  backdrop?: 'none' | 'ui'; // 'ui': blurred abstract dashboard panels behind the words
  backdropOpacity?: number; // 0-1, default 0.18
  faceHeight?: number; // face image height, % of the canvas height (default 96); >100 crops it
  faceTop?: number; // when set, anchor the face image this % from the top instead of the bottom
  faceInset?: number; // px from the side edge, default 20 (negative pushes it off-canvas)
  // 'headline-chips' only (text is the fallback headline when `headline` is absent)
  kicker?: KickerPart[]; // white pill top-left, e.g. a plain-text brand word + "CAREER 2026"
  headline?: HeadlinePart[]; // one big line, each part its own colour
  highlight?: ThumbHighlight; // the tilted box under the headline
  chips?: ThumbChip[];
  card?: ThumbCard; // small white ticket-style card at the end of the chip row
  tags?: ThumbTag[];
  headingFont?: string; // overrides brand.font_heading for this layout
  headlineSize?: number; // px at 1280x720, default 150
  highlightSize?: number; // px, default 190
  bgEdge?: string; // left-edge colour of the background gradient (bgColor = middle, glowColor = right)
  rays?: boolean; // faint sunburst behind the presenter, default true
  assetBase?: string;
};

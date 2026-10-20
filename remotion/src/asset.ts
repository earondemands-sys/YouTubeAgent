import {staticFile} from 'remotion';

// Project files are served over HTTP during a render (scripts/render.py sets assetBase); in the
// Studio they fall back to the public folder.
export const asset = (src: string, base?: string): string =>
  base ? base + src.split('/').map(encodeURIComponent).join('/') : staticFile(src);

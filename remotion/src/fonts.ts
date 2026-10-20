import {loadFont as anton} from '@remotion/google-fonts/Anton';
import {loadFont as bebas} from '@remotion/google-fonts/BebasNeue';
import {loadFont as inter} from '@remotion/google-fonts/Inter';
import {loadFont as montserrat} from '@remotion/google-fonts/Montserrat';
import {loadFont as notoTelugu} from '@remotion/google-fonts/NotoSansTelugu';
import {loadFont as oswald} from '@remotion/google-fonts/Oswald';
import {loadFont as poppins} from '@remotion/google-fonts/Poppins';

// Only the weights the designs use, so a render does not download every cut of every family.
const LOADERS: Record<string, () => {fontFamily: string}> = {
  Montserrat: () => montserrat('normal', {weights: ['600', '800', '900'], subsets: ['latin']}),
  Inter: () => inter('normal', {weights: ['500', '700', '800'], subsets: ['latin']}),
  Poppins: () => poppins('normal', {weights: ['600', '800', '900'], subsets: ['latin']}),
  Anton: () => anton('normal', {weights: ['400'], subsets: ['latin']}),
  'Bebas Neue': () => bebas('normal', {weights: ['400'], subsets: ['latin']}),
  Oswald: () => oswald('normal', {weights: ['600', '700'], subsets: ['latin']}),
};

const loaded: Record<string, string> = {};
let telugu: string | null = null;

// A font family stack for `name`, with Telugu script covered whatever the brand font is.
export const fontStack = (name?: string): string => {
  const key = name && LOADERS[name] ? name : 'Montserrat';
  if (!loaded[key]) {
    loaded[key] = LOADERS[key]().fontFamily;
  }
  if (!telugu) {
    telugu = notoTelugu('normal', {weights: ['700', '800']}).fontFamily;
  }
  return `"${loaded[key]}", "${telugu}", sans-serif`;
};

// The golden angle keeps neighbouring boat numbers far apart on the colour wheel.
const GOLDEN_ANGLE = 137.508;
// Orange is reserved for suspect legs.
const ORANGE_START = 15;
const ORANGE_WIDTH = 30;
const USABLE_HUES = 360 - ORANGE_WIDTH;
const LIGHTNESS_LEVELS = [42, 30, 52];
const SATURATION = 85;

function boatNumber(slug) {
  const digits = slug.match(/\d+/);
  if (digits !== null) {
    return Number(digits[0]);
  }
  return [...slug].reduce((sum, char) => sum + char.charCodeAt(0), 0);
}

export function boatHue(slug) {
  const hue = (boatNumber(slug) * GOLDEN_ANGLE) % USABLE_HUES;
  return hue >= ORANGE_START ? hue + ORANGE_WIDTH : hue;
}

export function boatColor(slug) {
  const lightness = LIGHTNESS_LEVELS[boatNumber(slug) % LIGHTNESS_LEVELS.length];
  return `hsl(${boatHue(slug).toFixed(1)}, ${SATURATION}%, ${lightness}%)`;
}

// The Spreiding of a Veldslag: the standard deviation (km) of its Plaatshints around their
// middle. A small one means its articles name places close together, so its position says
// more. A range on it narrows the list and the map; its value sizes the square.

// The slider runs over STEPS steps on a log scale: step 0 is 0 km, then 10^(step/20) km,
// so 20 is 10 km, 40 is 100 km and the last step, 60, is "1000 km and more".
export const STEPS = 60;
const PER_DECADE = 20;

export function kmForStep(step) {
  return step <= 0 ? 0 : Math.round(10 ** (step / PER_DECADE));
}

export function stepForKm(km) {
  if (km <= 0) return 0;
  return Math.max(1, Math.min(STEPS, Math.round(Math.log10(km) * PER_DECADE)));
}

// A range is { min, max } in km; max null is open (no upper bound). The full range lets all through.
export const FULL_RANGE = { min: 0, max: null };

export function rangeForSteps(low, high) {
  return { min: kmForStep(low), max: high >= STEPS ? null : kmForStep(high) };
}

export function isFull(range) {
  return range.min <= 0 && range.max === null;
}

// A battle without Plaatshints (no summary) is always shown: the range only judges a spread.
export function inSpreadRange(summary, range) {
  if (!summary || isFull(range)) return true;
  return summary.spread_km >= range.min && (range.max === null || summary.spread_km <= range.max);
}

export function rangeText(range) {
  const high = range.max === null ? "1000+" : String(range.max);
  return `Spreiding ${range.min}–${high} km`;
}

// The side of a square in px: 10 as now for a battle without hints and at 100 km, larger for a
// small spread (about 13 at 20 km, 14 at most), smaller for a wide one (about 7 at 500 km, 6 at least).
export const PLAIN_SIZE = 10;

export function squareSize(summary) {
  if (!summary) return PLAIN_SIZE;
  const size = PLAIN_SIZE - 4 * Math.log10(Math.max(summary.spread_km, 1) / 100);
  return Math.round(Math.min(14, Math.max(6, size)));
}

// "20-150" in the URL, "20-" for an open top; null for the full range.
export function writeRange(range) {
  if (isFull(range)) return null;
  return `${range.min}-${range.max ?? ""}`;
}

export function readRange(text) {
  const match = /^(\d+)-(\d*)$/.exec(text ?? "");
  if (!match) return FULL_RANGE;
  const min = Number(match[1]);
  const max = match[2] === "" ? null : Number(match[2]);
  if (max !== null && max < min) return FULL_RANGE;
  return { min, max };
}

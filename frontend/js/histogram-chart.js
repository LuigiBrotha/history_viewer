// Where the bars of /histogram go: one stacked bar per length, a block per Benaming, the rough
// part (known only by month or year) of each block above its precise part. Pure: no canvas.

export const MARGIN = { top: 16, right: 16, bottom: 44, left: 52 };
const MAX_BAR = 88;
const BAR_SHARE = 0.62;

// The top of the axis: 1, 2, 2.5, 3 or 5 times a power of ten, at or above `value`.
export function niceMax(value) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 3, 5, 10].find((f) => f * power >= value);
  return step * power;
}

function columns(bars, width) {
  const plotWidth = Math.max(10, width - MARGIN.left - MARGIN.right);
  const step = plotWidth / bars.length;
  const barWidth = Math.min(MAX_BAR, step * BAR_SHARE);
  return { step, barWidth, x: (index) => MARGIN.left + index * step + (step - barWidth) / 2 };
}

// Rectangles from the baseline up: { bar, segment, rough, x, width, y0 (top), y1 (bottom), isTop }.
export function layout(bars, width, height) {
  const top = niceMax(Math.max(0, ...bars.map((bar) => bar.total)));
  const plotHeight = Math.max(10, height - MARGIN.top - MARGIN.bottom);
  const baseline = MARGIN.top + plotHeight;
  const y = (count) => baseline - (count / top) * plotHeight;
  const { barWidth, x } = columns(bars, width);
  const rects = [];
  bars.forEach((bar, barIndex) => {
    let below = 0;
    const own = [];
    bar.segments.forEach((segment, segmentIndex) => {
      const precise = segment.battles.length - segment.rough;
      for (const [count, rough] of [[precise, false], [segment.rough, true]]) {
        if (count === 0) continue;
        own.push({ bar: barIndex, segment: segmentIndex, rough, x: x(barIndex), width: barWidth,
          y0: y(below + count), y1: y(below), isTop: false });
        below += count;
      }
    });
    if (own.length) own.at(-1).isTop = true;
    rects.push(...own);
  });
  return { top, y, baseline, plotHeight, rects, x, barWidth };
}

// What lies under the pointer: { bar, segment } on a block, { bar, segment: null } in a bar's
// column above or between its blocks, null outside every column.
export function hitTest(rects, bars, width, height, px, py) {
  const { step } = columns(bars, width);
  const bar = Math.floor((px - MARGIN.left) / step);
  if (bar < 0 || bar >= bars.length || py < MARGIN.top || py > height - MARGIN.bottom) return null;
  const hit = rects.find((r) => r.bar === bar && px >= r.x && px <= r.x + r.width && py >= r.y0 && py <= r.y1);
  return { bar, segment: hit ? hit.segment : null };
}

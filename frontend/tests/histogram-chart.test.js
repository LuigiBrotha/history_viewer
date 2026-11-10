import { test } from "node:test";
import assert from "node:assert/strict";

import { MARGIN, hitTest, layout, niceMax } from "../js/histogram-chart.js";

// Two bars: the first with 6 Battles (2 rough) and 2 Operations, the second with 4 Operations.
const bars = [
  { name: "1 dag", total: 8, segments: [{ benaming: "battle", battles: Array(6), rough: 2 }, { benaming: "operation", battles: Array(2), rough: 0 }] },
  { name: "2–3 dagen", total: 4, segments: [{ benaming: "battle", battles: [], rough: 0 }, { benaming: "operation", battles: Array(4), rough: 0 }] },
];
const width = MARGIN.left + MARGIN.right + 200;
const height = MARGIN.top + MARGIN.bottom + 100;

test("the axis rounds up to a readable number", () => {
  assert.equal(niceMax(8), 10);
  assert.equal(niceMax(816), 1000);
  assert.equal(niceMax(300), 300);
  assert.equal(niceMax(0), 1);
});

test("each bar stacks its Benamingen from the baseline, the rough part on top of each", () => {
  const { top, rects } = layout(bars, width, height);
  assert.equal(top, 10);
  const baseline = MARGIN.top + 100;
  const first = rects.filter((r) => r.bar === 0);
  // Battle: 4 precise and 2 rough, then Operation: 2 precise. 10 Veldslagen are 100 px.
  assert.deepEqual(first.map((r) => [r.segment, r.rough, r.y0, r.y1]), [
    [0, false, baseline - 40, baseline],
    [0, true, baseline - 60, baseline - 40],
    [1, false, baseline - 80, baseline - 60],
  ]);
  assert.equal(first.at(-1).isTop, true);
  assert.equal(first[0].isTop, false);
  // An empty segment draws nothing.
  assert.deepEqual(rects.filter((r) => r.bar === 1).map((r) => r.segment), [1]);
  // Both bars lie side by side, each in its own column.
  assert.ok(rects.find((r) => r.bar === 1).x > first[0].x + first[0].width);
});

test("the pointer finds the segment under it, or only the bar above the stack", () => {
  const { rects } = layout(bars, width, height);
  const battle = rects.find((r) => r.bar === 0 && r.segment === 0 && r.rough);
  const midX = battle.x + battle.width / 2;
  assert.deepEqual(hitTest(rects, bars, width, height, midX, (battle.y0 + battle.y1) / 2), { bar: 0, segment: 0 });
  assert.deepEqual(hitTest(rects, bars, width, height, midX, MARGIN.top + 1), { bar: 0, segment: null });
  assert.equal(hitTest(rects, bars, width, height, 1, MARGIN.top + 50), null);
});

import { test } from "node:test";
import assert from "node:assert/strict";

import { starPath, starPoints } from "../js/ship-star.js";

test("a ship's star has six arms around its point, the first straight up", () => {
  const points = starPoints(100, 50, 6);
  assert.equal(points.length, 12);
  // Arms at full radius, the notches between them close to the centre: it reads as a *.
  assert.deepEqual(points[0].map((v) => Math.round(v * 100) / 100), [100, 44]);
  const distance = ([x, y]) => Math.hypot(x - 100, y - 50);
  for (let i = 0; i < 12; i += 2) assert.ok(Math.abs(distance(points[i]) - 6) < 1e-9);
  for (let i = 1; i < 12; i += 2) assert.ok(distance(points[i]) < 3);
});

test("the star is one closed SVG path", () => {
  const d = starPath(10, 10, 6);
  assert.match(d, /^M[\d.\-]+ [\d.\-]+(L[\d.\-]+ [\d.\-]+){11}Z$/);
});

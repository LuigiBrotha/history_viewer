import { test } from "node:test";
import assert from "node:assert/strict";

import { turboColor, rampGradient } from "../js/color-ramp.js";

function channels(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

test("turboColor starts dark purple-blue, passes green and ends dark red", () => {
  const [lowR, lowG, lowB] = channels(turboColor(0));
  assert.ok(lowR < 60 && lowG < 40 && lowB < 50);
  const [midR, midG, midB] = channels(turboColor(0.5));
  assert.ok(midG > 200 && midG > midB && midR > 100);
  const [highR, highG, highB] = channels(turboColor(1));
  assert.ok(highR > 100 && highG < 30 && highB < 30);
});

test("turboColor clamps values outside the ramp", () => {
  assert.equal(turboColor(-1), turboColor(0));
  assert.equal(turboColor(2), turboColor(1));
});

test("turboColor returns a valid hex colour along the whole ramp", () => {
  for (let i = 0; i <= 100; i++) {
    assert.match(turboColor(i / 100), /^#[0-9a-f]{6}$/);
  }
});

test("rampGradient runs from the lowest to the highest colour", () => {
  const gradient = rampGradient();
  assert.ok(gradient.startsWith(`linear-gradient(to right, ${turboColor(0)}`));
  assert.ok(gradient.endsWith(`${turboColor(1)})`));
});

import { test } from "node:test";
import assert from "node:assert/strict";

import { boatColor, boatHue } from "../js/boat-color.js";

test("boatColor is stable for a boat", () => {
  assert.equal(boatColor("u99"), boatColor("u99"));
});

test("boatColor gives neighbouring boat numbers clearly different hues", () => {
  for (let n = 1; n < 200; n++) {
    const distance = Math.abs(boatHue(`u${n}`) - boatHue(`u${n + 1}`));
    assert.ok(Math.min(distance, 360 - distance) > 40, `u${n}`);
  }
});

test("boatColor never uses the orange of a suspect leg", () => {
  for (let n = 1; n <= 1300; n++) {
    const hue = boatHue(`u${n}`);
    assert.ok(hue < 15 || hue >= 45, `u${n} has hue ${hue}`);
  }
});

test("boatColor tells most of the fleet apart", () => {
  const colors = new Set();
  for (let n = 1; n <= 1153; n++) {
    colors.add(boatColor(`u${n}`));
  }
  assert.ok(colors.size > 1000);
});

test("boatColor handles a slug without a number", () => {
  assert.match(boatColor("ua"), /^hsl\(/);
});

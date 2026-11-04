import { test } from "node:test";
import assert from "node:assert/strict";

import { sliderValueForDate } from "../js/timeline.js";

test("sliderValueForDate is zero for the range minimum", () => {
  const min = new Date(Date.UTC(1940, 5, 1));
  assert.equal(sliderValueForDate(min, min), 0);
});

test("sliderValueForDate keeps the same date after the range starts earlier", () => {
  const date = new Date(Date.UTC(1940, 5, 10));
  const before = sliderValueForDate(new Date(Date.UTC(1940, 5, 1)), date);
  const after = sliderValueForDate(new Date(Date.UTC(1940, 4, 1)), date);
  assert.equal(before, 9);
  assert.equal(after, 40);
});

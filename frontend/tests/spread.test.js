import { test } from "node:test";
import assert from "node:assert/strict";

import {
  FULL_RANGE, PLAIN_SIZE, STEPS, inSpreadRange, kmForStep, rangeForSteps, rangeText, readRange, squareSize, stepForKm, writeRange,
} from "../js/spread.js";

test("the slider steps are logarithmic, 0 is 0 km and the last step is open", () => {
  assert.equal(kmForStep(0), 0);
  assert.equal(kmForStep(20), 10);
  assert.equal(kmForStep(40), 100);
  assert.equal(stepForKm(100), 40);
  assert.equal(stepForKm(0), 0);
  assert.deepEqual(rangeForSteps(0, STEPS), FULL_RANGE);
  assert.deepEqual(rangeForSteps(26, 43), { min: 20, max: 141 });
});

test("a battle without hints is always in range; others by their spread", () => {
  const range = { min: 20, max: 150 };
  assert.equal(inSpreadRange(undefined, range), true);
  assert.equal(inSpreadRange({ spread_km: 20 }, range), true);
  assert.equal(inSpreadRange({ spread_km: 151 }, range), false);
  assert.equal(inSpreadRange({ spread_km: 5000 }, { min: 20, max: null }), true);
  assert.equal(inSpreadRange({ spread_km: 0 }, FULL_RANGE), true);
});

test("squares grow a little for a small spread and shrink a little for a wide one", () => {
  assert.equal(squareSize(undefined), PLAIN_SIZE);
  assert.equal(squareSize({ spread_km: 100 }), 10);
  assert.equal(squareSize({ spread_km: 20 }), 13);
  assert.equal(squareSize({ spread_km: 500 }), 7);
  assert.equal(squareSize({ spread_km: 0 }), 14);
  assert.equal(squareSize({ spread_km: 100000 }), 6);
});

test("the range is written for the URL and read back; nonsense is the full range", () => {
  assert.equal(writeRange(FULL_RANGE), null);
  assert.equal(writeRange({ min: 20, max: 150 }), "20-150");
  assert.equal(writeRange({ min: 20, max: null }), "20-");
  assert.deepEqual(readRange("20-150"), { min: 20, max: 150 });
  assert.deepEqual(readRange("20-"), { min: 20, max: null });
  assert.deepEqual(readRange("150-20"), FULL_RANGE);
  assert.deepEqual(readRange("x"), FULL_RANGE);
  assert.equal(rangeText({ min: 0, max: null }), "Spreiding 0–1000+ km");
});

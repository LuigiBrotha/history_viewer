import { test } from "node:test";
import assert from "node:assert/strict";

import { loadPercent, loadDetail } from "../js/load-indicator.js";

test("loadPercent rounds down and stays below 100 until loading is finished", () => {
  assert.equal(loadPercent(0, 100), 0);
  assert.equal(loadPercent(419, 1000), 41);
  assert.equal(loadPercent(1000, 1000), 99);
  assert.equal(loadPercent(1200, 1000), 99);
});

test("loadPercent is zero while the total is unknown", () => {
  assert.equal(loadPercent(0, 0), 0);
  assert.equal(loadPercent(5, null), 0);
});

test("loadDetail shows what has arrived", () => {
  assert.equal(loadDetail(419, 1000), "419 van 1000 patrouilles");
  assert.equal(loadDetail(1002, 1000), "1000 van 1000 patrouilles");
  assert.equal(loadDetail(0, null), "Verbinden…");
});

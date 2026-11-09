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

import { createLoadIndicator } from "../js/load-indicator.js";
import { Element, installDom } from "./battle-dom.js";

test("after the first page the indicator shrinks, and it goes when all have arrived", async () => {
  installDom();
  const rootEl = new Element("div");
  const indicator = createLoadIndicator(rootEl);
  const page = (count) => Array.from({ length: count }, (_, i) => ({ external_id: `p${i}` }));
  const pages = [page(350), page(1)];
  globalThis.fetch = async () => ({ ok: true, json: async () => pages.shift() });
  const seen = [];
  assert.equal(indicator.complete(), false);
  const result = await indicator.fetchRoutes(null, () => {
    seen.push([indicator.complete(), rootEl.hidden]);
    indicator.finish();
    seen.push(rootEl.classes.has("background"));
  });
  assert.equal(result, null);
  assert.deepEqual(seen, [[false, false], true, [true, false], true]);
  assert.equal(rootEl.hidden, true);
});

test("firstDrawn waits for the first page, and does not hang when loading fails", async () => {
  installDom();
  const indicator = createLoadIndicator(new Element("div"));
  let resolved = false;
  indicator.firstDrawn.then(() => (resolved = true));
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(resolved, false);
  indicator.finish();
  await new Promise((r) => setTimeout(r, 5));
  assert.equal(resolved, true);

  const failing = createLoadIndicator(new Element("div"));
  globalThis.fetch = async () => ({ ok: false, status: 500 });
  await assert.rejects(() => failing.fetchRoutes(null));
  await failing.firstDrawn;
});

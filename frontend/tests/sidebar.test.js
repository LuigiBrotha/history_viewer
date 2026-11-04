import { test } from "node:test";
import assert from "node:assert/strict";

import { boatsHeading, renderExcludedPoints } from "../js/sidebar.js";
import { installFakeDom } from "./fake-dom.js";

test("boatsHeading shows how many boats are active", () => {
  assert.equal(boatsHeading(33), "Actieve boten (33)");
  assert.equal(boatsHeading(0), "Actieve boten (0)");
});

const excludedPatrol = {
  external_id: "p1",
  excluded_points: [
    { sequence: 2, lat: 51, lng: -4, date: "1940-06-19" },
    { sequence: 5, lat: 52.1234, lng: -3, date: null },
  ],
};

test("renderExcludedPoints lists excluded points as text, each with Herstellen", () => {
  const listEl = installFakeDom();
  const restored = [];
  renderExcludedPoints({ listEl, patrol: excludedPatrol, onRestore: (point) => restored.push(point.sequence), isBusy: () => false });
  assert.equal(listEl.hidden, false);
  const [heading] = listEl.find("h3");
  assert.equal(heading.textContent, "Uitgesloten punten");
  const spans = listEl.find("span").map((s) => s.textContent);
  assert.deepEqual(spans, ["1940-06-19 (51.000, -4.000)", "geen datum (52.123, -3.000)"]);
  const buttons = listEl.find("button");
  assert.deepEqual(buttons.map((b) => b.textContent), ["Herstellen", "Herstellen"]);
  buttons[1].click();
  assert.deepEqual(restored, [5]);
});

test("renderExcludedPoints hides the list without excluded points and omits Herstellen when read-only", () => {
  const listEl = installFakeDom();
  renderExcludedPoints({ listEl, patrol: { external_id: "p1", excluded_points: [] }, onRestore: null, isBusy: () => false });
  assert.equal(listEl.hidden, true);
  assert.equal(listEl.children.length, 0);
  renderExcludedPoints({ listEl, patrol: excludedPatrol, onRestore: null, isBusy: () => false });
  assert.equal(listEl.hidden, false);
  assert.equal(listEl.find("button").length, 0);
  assert.equal(listEl.find("span").length, 2);
});

test("renderExcludedPoints keeps a point in flight busy across a rebuild", () => {
  const listEl = installFakeDom();
  let clicks = 0;
  const busy = (externalId, sequence) => externalId === "p1" && sequence === 5;
  renderExcludedPoints({ listEl, patrol: excludedPatrol, onRestore: () => clicks++, isBusy: busy });
  const [first, second] = listEl.find("button");
  assert.equal(first.textContent, "Herstellen");
  assert.equal(first.disabled, false);
  assert.equal(second.textContent, "Bezig…");
  assert.equal(second.disabled, true);
  second.click();
  assert.equal(clicks, 0);
});

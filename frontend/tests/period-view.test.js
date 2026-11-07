import { test } from "node:test";
import assert from "node:assert/strict";

import { createPeriodView } from "../js/period-view.js";

function fakes(search) {
  const writes = [];
  const urlSync = { update: (partial) => writes.push(partial) };
  const calls = [];
  const map = {
    listeners: {},
    setView: (center, zoom, options) => calls.push(["setView", center, zoom, options]),
    on(name, fn) {
      this.listeners[name] = fn;
    },
    getCenter: () => ({ lat: 10, lng: 20 }),
    getZoom: () => 4,
  };
  const slider = { setPeriod: (from, to) => calls.push(["setPeriod", from, to]) };
  let resolve = null;
  const battles = {
    selectBattle: (title, { onResolved }) => {
      calls.push(["selectBattle", title]);
      resolve = onResolved;
      return true;
    },
    setOnlyWithoutPosition: (on) => calls.push(["nopos", on]),
  };
  const view = createPeriodView({ search, urlSync, map });
  return { view, writes, calls, map, slider, battles, resolve: (found) => resolve(found) };
}

test("restores period, Alleen zonder positie, Veldslag and Kaartuitsnede", () => {
  const { view, calls, slider, battles } = fakes("?van=1941-01-01&tot=1941-12-31&veldslag=Second_Happy_Time&kaart=40,-40,4&zonderpositie=1");
  assert.equal(view.mapPinned(), true);
  view.restore({ slider, battles });
  assert.deepEqual(calls, [
    ["setPeriod", "1941-01-01", "1941-12-31"],
    ["nopos", true],
    ["selectBattle", "Second Happy Time"],
    ["setView", [40, -40], 4, { animate: false }],
  ]);
});

test("an empty URL restores nothing and pins no map", () => {
  const { view, calls, slider, battles } = fakes("");
  assert.equal(view.mapPinned(), false);
  view.restore({ slider, battles });
  assert.deepEqual(calls, []);
});

test("an open end of the period stays open", () => {
  const { view, calls, slider, battles } = fakes("?tot=1942-01-01");
  view.restore({ slider, battles });
  assert.deepEqual(calls, [["setPeriod", null, "1942-01-01"]]);
});

test("the pinned Kaartuitsnede wins over the pan to the restored battle, once", () => {
  const { view, calls, slider, battles, resolve } = fakes("?veldslag=Midway&kaart=1,2,6");
  view.restore({ slider, battles });
  calls.length = 0;
  view.onBattleChange("Midway");
  resolve(true);
  assert.deepEqual(calls, [["setView", [1, 2], 6, { animate: false }]]);
  view.onBattleChange("Midway");
  assert.equal(calls.length, 1);
});

test("an unknown battle leaves the URL", () => {
  const { view, writes, slider, battles, resolve } = fakes("?veldslag=Nope");
  view.restore({ slider, battles });
  writes.length = 0;
  resolve(false);
  assert.deepEqual(writes, [{ battle: null }]);
});

test("reports period, battle, filter and map moves to the URL", () => {
  const { view, writes, map, slider, battles } = fakes("");
  view.restore({ slider, battles });
  view.onPeriod({ from: "1941-01-01", to: null });
  view.onBattleChange("Midway");
  view.onNoposChange(true);
  view.onNoposChange(false);
  map.listeners.moveend();
  assert.deepEqual(writes, [
    { from: "1941-01-01", to: null },
    { battle: "Midway" },
    { nopos: true },
    { nopos: null },
    { map: { lat: 10, lng: 20, zoom: 4 } },
  ]);
});

test("labels and the sort order are restored, and their changes reach the URL", () => {
  const { view, writes, slider, battles } = fakes("?filter=land%3APolen%2Cwinnaar%3Aas&sorteer=duur");
  const calls = [];
  let labelListener;
  let sortListener;
  Object.assign(battles, {
    setLabels: (labels) => calls.push(["labels", labels]),
    setSort: (sort) => calls.push(["sort", sort]),
    onLabelsChange: (fn) => (labelListener = fn),
    onSortChange: (fn) => (sortListener = fn),
  });
  view.restore({ slider, battles });
  assert.deepEqual(calls, [
    ["labels", [{ kind: "land", value: "Polen" }, { kind: "winnaar", value: "as" }]],
    ["sort", "duur"],
  ]);
  writes.length = 0;
  labelListener([{ kind: "taal", value: "nl" }]);
  labelListener([]);
  sortListener("datum");
  sortListener("naam");
  assert.deepEqual(writes, [{ filter: "taal:nl" }, { filter: null }, { sort: null }, { sort: "naam" }]);
});

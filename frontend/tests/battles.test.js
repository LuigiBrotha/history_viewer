import { test } from "node:test";
import assert from "node:assert/strict";

import { initBattles } from "../js/battles.js";
import { Element, fakeStorage, installDom } from "./battle-dom.js";

const battle = (over = {}) => ({
  title: "Battle of Kursk",
  url: "https://en.wikipedia.org/wiki/Battle_of_Kursk",
  start: "1943-07-05",
  end: "1943-08-23",
  precision: "day",
  date_text: "5 July 1943 – 23 August 1943",
  lat: 51.7,
  lng: 36.1,
  part_of: null,
  place: null,
  ...over,
});

const BATTLES = [
  battle(),
  battle({ title: "Midway", start: "1942-06-04", end: "1942-06-07", lat: 30, lng: -178 }),
  battle({ title: "Atlantic", start: "1939-09-03", end: "1945-05-08", lat: null, lng: null }),
];

function setup({ mode = "date", load = async () => BATTLES, loadPositions = async () => [], width = 1200 } = {}) {
  installDom();
  const layers = new Set();
  const pans = [];
  globalThis.L = {
    divIcon: (options) => ({ ...options }),
    marker: (latlng, options) => {
      const marker = {
        latlng,
        options,
        events: {},
        on(type, fn) {
          marker.events[type] = fn;
          return marker;
        },
        bindTooltip() {
          return marker;
        },
        setIcon(icon) {
          marker.options = { ...marker.options, icon };
        },
      };
      return marker;
    },
    layerGroup: () => ({ addTo() { return this; }, addLayer: (l) => layers.add(l), removeLayer: (l) => layers.delete(l) }),
  };
  const map = {
    invalidations: 0,
    invalidateSize() { this.invalidations += 1; },
    on() {},
    getZoom: () => 4,
    getBounds: () => ({ getSouth: () => -90, getWest: () => -180, getNorth: () => 90, getEast: () => 180 }),
    panTo: (latlng) => pans.push(latlng),
  };
  const elements = {};
  for (const id of ["battle-split", "map-side", "battle-pane", "battle-divider", "battle-toggle"]) {
    elements[id] = new Element(id === "battle-pane" ? "aside" : "div");
  }
  elements["battle-split"].rect = { left: 0, top: 0, right: width, bottom: 800, width, height: 800 };
  const doc = { getElementById: (id) => elements[id] };
  const win = { innerWidth: width, innerHeight: 800, addEventListener() {}, requestAnimationFrame: (fn) => fn(), localStorage: fakeStorage() };
  const picked = [];
  const controller = initBattles({ map, mode, onPickDate: (iso) => picked.push(iso), doc, win, load, loadPositions });
  const squares = () => [...layers].filter((m) => m.options.icon.className.includes("battle-square")).map((m) => m.options.battleTitle).sort();
  const rows = () => elements["battle-pane"].byClass("battle-row");
  const titleOf = (row) => row.byClass("battle-row-title")[0].textContent;
  const ready = () => new Promise((resolve) => setImmediate(resolve));
  return { controller, elements, squares, rows, titleOf, picked, pans, map, ready, layers };
}

test("on the timeline page the squares are the battles active on the date", async () => {
  const { controller, squares, ready } = setup({ mode: "date" });
  await ready();
  controller.setDate("1942-06-05");
  assert.deepEqual(squares(), ["Midway"]);
  controller.setDate("1943-07-05");
  assert.deepEqual(squares(), ["Battle of Kursk"]);
  controller.setDate("1941-01-01");
  assert.deepEqual(squares(), []);
});

test("a date given before the file has loaded is applied when it arrives", async () => {
  const { controller, squares, rows, ready } = setup({ mode: "date" });
  controller.setDate("1942-06-05");
  assert.deepEqual(squares(), []);
  await ready();
  assert.deepEqual(squares(), ["Midway"]);
  assert.equal(rows().length, 3);
});

test("on the period pages the squares are the battles overlapping the period, all without one", async () => {
  const { controller, squares, ready } = setup({ mode: "period" });
  await ready();
  controller.setPeriod(null, null);
  assert.deepEqual(squares(), ["Battle of Kursk", "Midway"]);
  controller.setPeriod("1942-01-01", "1942-12-31");
  assert.deepEqual(squares(), ["Midway"]);
  controller.setPeriod("1943-08-23", null);
  assert.deepEqual(squares(), ["Battle of Kursk"]);
});

test("every battle stays in the list whatever the period", async () => {
  const { controller, rows, ready } = setup({ mode: "period" });
  await ready();
  controller.setPeriod("1942-01-01", "1942-12-31");
  assert.equal(rows().length, 3);
  assert.equal(rows().filter((r) => r.classes.has("dimmed")).length, 1);
});

test("a click on a row pans to the square and, on the timeline page, sets the date to its start", async () => {
  const { controller, rows, titleOf, picked, pans, ready } = setup({ mode: "date" });
  await ready();
  controller.setDate("1941-01-01");
  const midway = rows().find((r) => titleOf(r) === "Midway");
  midway.byClass("battle-row-title")[0].dispatch("click");
  assert.deepEqual(picked, ["1942-06-04"]);
  assert.deepEqual(pans, [[30, -178]]);
});

test("a click on a row of the period pages does not change the period", async () => {
  const { controller, rows, titleOf, picked, pans, ready } = setup({ mode: "period" });
  await ready();
  controller.setPeriod(null, null);
  rows().find((r) => titleOf(r) === "Midway").byClass("battle-row-title")[0].dispatch("click");
  assert.deepEqual(picked, []);
  assert.deepEqual(pans, [[30, -178]]);
});

test("a click on a row without a position changes nothing on the map", async () => {
  const { rows, titleOf, pans, ready } = setup({ mode: "period" });
  await ready();
  rows().find((r) => titleOf(r) === "Atlantic").byClass("battle-row-title")[0].dispatch("click");
  assert.deepEqual(pans, []);
});

test("a click on a square opens a hidden pane and scrolls to the row", async () => {
  const { controller, elements, rows, titleOf, layers, ready } = setup({ mode: "period", width: 800 });
  await ready();
  controller.setPeriod(null, null);
  assert.equal(elements["battle-split"].classes.has("pane-hidden"), true);
  const square = [...layers].find((m) => m.options.battleTitle === "Midway");
  square.events.click();
  assert.equal(elements["battle-split"].classes.has("pane-hidden"), false);
  const row = rows().find((r) => titleOf(r) === "Midway");
  assert.equal(row.classes.has("selected"), true);
  assert.equal(row.scrolled, 1);
});

test("when the file cannot be loaded the pane says so and the controller keeps working", async () => {
  const { controller, elements, squares, ready } = setup({
    load: async () => {
      throw new Error("offline");
    },
  });
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args);
  await ready();
  console.error = original;
  assert.match(elements["battle-pane"].allText(), /Veldslagen konden niet worden geladen\./);
  assert.doesNotThrow(() => controller.setDate("1942-06-05"));
  assert.deepEqual(squares(), []);
  assert.equal(errors.length, 1);
});

test("the button shows the pane, and the map is told", async () => {
  const { elements, map, ready } = setup({ width: 800 });
  await ready();
  const before = map.invalidations;
  elements["battle-toggle"].dispatch("click");
  assert.equal(elements["battle-split"].classes.has("pane-hidden"), false);
  assert.ok(map.invalidations > before);
});

test("a battle is drawn at its Eigen positie", async () => {
  const { controller, layers, ready } = setup({
    mode: "period",
    loadPositions: async () => [{ title: "Midway", lat: 5, lng: 6 }],
  });
  await ready();
  controller.setPeriod(null, null);
  const square = [...layers].find((m) => m.options.battleTitle === "Midway");
  assert.deepEqual(square.latlng, [5, 6]);
});

test("when the positions cannot be loaded the squares from the file are still drawn", async () => {
  const { controller, squares, ready } = setup({
    mode: "period",
    loadPositions: async () => {
      throw new Error("offline");
    },
  });
  const errors = [];
  const original = console.error;
  console.error = (...args) => errors.push(args);
  await ready();
  console.error = original;
  controller.setPeriod(null, null);
  assert.deepEqual(squares(), ["Battle of Kursk", "Midway"]);
  assert.equal(errors.length, 1);
});

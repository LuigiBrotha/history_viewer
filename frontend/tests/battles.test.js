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

function setup({ mode = "date", load = async () => BATTLES, loadPositions = async () => [], width = 1200, savePosition = async () => {}, clearPosition = async () => {}, loadArticle = async (title) => ({ html: "", url: `https://en.wikipedia.org/wiki/${title}` }) } = {}) {
  installDom();
  const layers = new Set();
  const pans = [];
  const controls = [];
  globalThis.L = {
    control: (options) => {
      const control = {
        options,
        onAdd: null,
        removed: false,
        addTo() {
          control.el = control.onAdd();
          controls.push(control);
          return control;
        },
        remove() {
          control.removed = true;
        },
      };
      return control;
    },
    DomEvent: { disableClickPropagation() {} },
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
        dragging: { enable() {}, disable() {} },
        setLatLng(latlng) {
          marker.latlng = latlng;
          return marker;
        },
        getLatLng: () => ({ lat: marker.latlng[0], lng: marker.latlng[1] }),
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
    getCenter: () => ({ lat: 10, lng: 20 }),
    getBounds: () => ({ getSouth: () => -90, getWest: () => -180, getNorth: () => 90, getEast: () => 180 }),
    panTo: (latlng) => pans.push(latlng),
    setView: (latlng) => pans.push(latlng),
  };
  const elements = {};
  for (const id of ["battle-split", "map-side", "battle-pane", "battle-divider", "battle-toggle", "article-split", "article-pane", "article-divider"]) {
    elements[id] = new Element(id.endsWith("-pane") ? "aside" : "div");
  }
  elements["battle-split"].rect = { left: 0, top: 0, right: width, bottom: 800, width, height: 800 };
  const keyHandlers = new Set();
  const doc = {
    getElementById: (id) => elements[id],
    createElement: (tag) => new Element(tag),
    addEventListener: (type, fn) => keyHandlers.add(fn),
    removeEventListener: (type, fn) => keyHandlers.delete(fn),
  };
  const press = (key, target = null) => [...keyHandlers].forEach((fn) => fn({ key, target }));
  const win = { innerWidth: width, innerHeight: 800, addEventListener() {}, requestAnimationFrame: (fn) => fn(), localStorage: fakeStorage() };
  elements["article-split"].rect = elements["battle-split"].rect;
  const picked = [];
  const changes = [];
  const articles = [];
  const controller = initBattles({
    map,
    mode,
    onPickDate: (iso) => picked.push(iso),
    onBattleChange: (title) => changes.push(title),
    doc,
    win,
    load,
    loadPositions,
    savePosition,
    clearPosition,
    loadArticle: async (title) => {
      articles.push(title);
      return loadArticle(title);
    },
  });
  const squares = () => [...layers].filter((m) => m.options.icon.className.includes("battle-square")).map((m) => m.options.battleTitle).sort();
  const rows = () => elements["battle-pane"].byClass("battle-row");
  const titleOf = (row) => row.byClass("battle-row-title")[0].textContent;
  const ready = () => new Promise((resolve) => setImmediate(resolve));
  return { controller, changes, articles, elements, squares, rows, titleOf, picked, pans, map, ready, layers, controls, press };
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

test("selectBattle selects like a row click, without picking the date", async () => {
  const { controller, elements, rows, titleOf, picked, pans, ready } = setup({ mode: "date", width: 800 });
  await ready();
  assert.equal(controller.selectBattle("Midway"), true);
  assert.deepEqual(picked, []);
  assert.deepEqual(pans, [[30, -178]]);
  assert.equal(elements["battle-split"].classes.has("pane-hidden"), false);
  const row = rows().find((r) => titleOf(r) === "Midway");
  assert.equal(row.classes.has("selected"), true);
  assert.equal(row.scrolled, 1);
});

test("selectBattle returns false for an unknown title and changes nothing", async () => {
  const { controller, rows, titleOf, pans, ready } = setup({ mode: "period" });
  await ready();
  assert.equal(controller.selectBattle("Nope"), false);
  assert.deepEqual(pans, []);
  assert.equal(rows().some((r) => r.classes.has("selected")), false);
  assert.equal(titleOf(rows()[0]).length > 0, true);
});

test("allBattles gives the battles with their Eigen posities", async () => {
  const { controller, ready } = setup({ loadPositions: async () => [{ title: "Midway", lat: 1, lng: 2 }] });
  assert.deepEqual(controller.allBattles(), []);
  await ready();
  const all = controller.allBattles();
  assert.equal(all.length, 3);
  assert.equal(all.find((b) => b.title === "Midway").lat, 1);
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

// Editing

async function startEditing(over = {}, title = "Midway") {
  const env = setup({ mode: "period", ...over });
  await env.ready();
  env.controller.setPeriod(null, null);
  env.controller.setEditable(true);
  const rowOf = () => env.rows().find((r) => env.titleOf(r) === title);
  rowOf().byClass("battle-row-title")[0].dispatch("click");
  rowOf().byClass("battle-row-edit")[0].dispatch("click");
  const squareOf = () => [...env.layers].find((m) => m.options.battleTitle === title);
  const bar = env.controls[0].el;
  const button = (name) => bar.byClass(name)[0];
  const drag = (lat, lng) => {
    const square = squareOf();
    square.latlng = [lat, lng];
    square.events.dragend();
  };
  return { ...env, rowOf, squareOf, bar, button, drag };
}

test("the edit bar names the battle as text and offers Bewaar and Annuleer", async () => {
  const { bar, controls } = await startEditing();
  assert.equal(controls[0].options.position, "topleft");
  assert.ok(bar.classes.has("battle-edit-bar"));
  assert.equal(bar.byClass("battle-edit-title")[0].textContent, "Midway");
  assert.equal(bar.byClass("battle-edit-save")[0].textContent, "Bewaar");
  assert.equal(bar.byClass("battle-edit-cancel")[0].textContent, "Annuleer");
});

test("Bewaar sends the dragged position and the square becomes an own one", async () => {
  const saved = [];
  const { button, controls, squareOf, rowOf, drag, ready } = await startEditing({ savePosition: async (...args) => saved.push(args) });
  drag(1, 2);
  button("battle-edit-save").dispatch("click");
  await ready();
  assert.deepEqual(saved, [["Midway", 1, 2]]);
  assert.equal(controls[0].removed, true);
  assert.deepEqual(squareOf().latlng, [1, 2]);
  assert.ok(squareOf().options.icon.className.includes("own"));
  assert.equal(rowOf().byClass("battle-ownpos")[0].textContent, "eigen positie");
  assert.equal(rowOf().classes.has("selected"), true);
});

test("a battle without a position is saved where it was dropped", async () => {
  const saved = [];
  const { button, ready } = await startEditing({ savePosition: async (...args) => saved.push(args) }, "Atlantic");
  button("battle-edit-save").dispatch("click");
  await ready();
  assert.deepEqual(saved, [["Atlantic", 10, 20]]);
});

test("a failed save says so, keeps the edit and keeps the dragged place", async () => {
  const { button, bar, controls, squareOf, drag, ready } = await startEditing({
    savePosition: async () => {
      throw new Error("403");
    },
  });
  const original = console.error;
  console.error = () => {};
  drag(1, 2);
  button("battle-edit-save").dispatch("click");
  assert.equal(button("battle-edit-save").disabled, true);
  await ready();
  console.error = original;
  const message = bar.byClass("battle-edit-error")[0];
  assert.equal(message.hidden, false);
  assert.equal(message.textContent, "Bewaren mislukt.");
  assert.equal(button("battle-edit-save").disabled, false);
  assert.equal(button("battle-edit-cancel").disabled, false);
  assert.equal(controls[0].removed, false);
  assert.deepEqual(squareOf().latlng, [1, 2]);
});

test("Annuleer and Esc restore the old place", async () => {
  for (const cancel of ["button", "esc"]) {
    const saved = [];
    const { button, controls, squareOf, drag, press } = await startEditing({ savePosition: async (...args) => saved.push(args) });
    drag(1, 2);
    if (cancel === "button") button("battle-edit-cancel").dispatch("click");
    else press("Escape");
    assert.equal(controls[0].removed, true);
    assert.deepEqual(squareOf().latlng, [30, -178]);
    assert.deepEqual(saved, []);
  }
});

test("Esc inside the map search field does not cancel the edit", async () => {
  const { controls, press } = await startEditing();
  const inSearch = { closest: (selector) => (selector === ".map-search" ? {} : null) };
  press("Escape", inSearch);
  assert.equal(controls[0].removed, false);
  press("Escape", { closest: () => null });
  assert.equal(controls[0].removed, true);
});

test("other keys do not cancel the edit", async () => {
  const { controls, press } = await startEditing();
  press("a");
  assert.equal(controls[0].removed, false);
});

test("clearing an Eigen positie restores the Wikipedia position", async () => {
  const cleared = [];
  const { controller, layers, rows, titleOf, ready } = setup({
    mode: "period",
    loadPositions: async () => [{ title: "Midway", lat: 5, lng: 6 }],
    clearPosition: async (title) => cleared.push(title),
  });
  await ready();
  controller.setPeriod(null, null);
  controller.setEditable(true);
  const row = () => rows().find((r) => titleOf(r) === "Midway");
  row().byClass("battle-row-title")[0].dispatch("click");
  row().byClass("battle-row-clear")[0].dispatch("click");
  await ready();
  assert.deepEqual(cleared, ["Midway"]);
  const square = [...layers].find((m) => m.options.battleTitle === "Midway");
  assert.deepEqual(square.latlng, [30, -178]);
  assert.equal(square.options.icon.className.includes("own"), false);
  assert.equal(row().byClass("battle-ownpos").length, 0);
  assert.equal(row().byClass("battle-row-clear").length, 0);
});

test("setEditable(false) cancels the edit and hides the buttons", async () => {
  const { controller, controls, squareOf, rowOf, drag } = await startEditing();
  drag(1, 2);
  controller.setEditable(false);
  assert.equal(controls[0].removed, true);
  assert.deepEqual(squareOf().latlng, [30, -178]);
  assert.equal(rowOf().byClass("battle-row-actions").length, 0);
});

test("selecting another battle cancels the edit", async () => {
  const { controls, rows, titleOf } = await startEditing();
  rows().find((r) => titleOf(r) === "Battle of Kursk").byClass("battle-row-title")[0].dispatch("click");
  assert.equal(controls[0].removed, true);
});

test("the buttons are not offered before the positions have loaded or when they failed to load", async () => {
  const original = console.error;
  console.error = () => {};
  const { controller, rows, titleOf, ready } = setup({
    mode: "period",
    loadPositions: async () => {
      throw new Error("offline");
    },
  });
  await ready();
  console.error = original;
  controller.setPeriod(null, null);
  controller.setEditable(true);
  rows().find((r) => titleOf(r) === "Midway").byClass("battle-row-title")[0].dispatch("click");
  assert.equal(rows().flatMap((r) => r.byClass("battle-row-edit")).length, 0);
});

const clickRow = (ctx, title) => ctx.rows().find((r) => ctx.titleOf(r) === title).byClass("battle-row-title")[0].dispatch("click");
const articleTitle = (ctx) => ctx.elements["article-pane"].byClass("article-title")[0].textContent;

test("a click on a row shows the article and tells the page", async () => {
  const ctx = setup({ mode: "period" });
  await ctx.ready();
  clickRow(ctx, "Battle of Kursk");
  assert.equal(ctx.elements["article-split"].classes.has("pane-hidden"), false);
  assert.equal(articleTitle(ctx), "Battle of Kursk");
  assert.deepEqual(ctx.articles, ["Battle of Kursk"]);
  assert.deepEqual(ctx.changes, ["Battle of Kursk"]);
  assert.equal(ctx.controller.selectedBattle(), "Battle of Kursk");
});

test("a click on a square shows the article without setting the date", async () => {
  const ctx = setup({ mode: "date" });
  await ctx.ready();
  ctx.controller.setDate("1942-06-05");
  [...ctx.layers].find((m) => m.options.battleTitle === "Midway").events.click();
  assert.equal(articleTitle(ctx), "Midway");
  assert.equal(ctx.elements["article-split"].classes.has("pane-hidden"), false);
  assert.deepEqual(ctx.picked, []);
});

test("the close button closes the article, and the next click opens it again", async () => {
  const ctx = setup({ mode: "period" });
  await ctx.ready();
  clickRow(ctx, "Midway");
  ctx.elements["article-pane"].byClass("article-close")[0].dispatch("click");
  assert.equal(ctx.controller.selectedBattle(), null);
  assert.equal(ctx.elements["article-split"].classes.has("pane-hidden"), true);
  assert.deepEqual(ctx.changes, ["Midway", null]);
  clickRow(ctx, "Midway");
  assert.equal(ctx.elements["article-split"].classes.has("pane-hidden"), false);
  assert.equal(ctx.controller.selectedBattle(), "Midway");
});

test("a battle selected before the file has loaded is applied when it arrives", async () => {
  const ctx = setup({ mode: "period" });
  assert.equal(ctx.controller.selectBattle("Midway"), true);
  assert.equal(ctx.controller.selectedBattle(), null);
  await ctx.ready();
  assert.equal(ctx.controller.selectedBattle(), "Midway");
  assert.deepEqual(ctx.changes, ["Midway"]);
});

test("an unknown title changes nothing", async () => {
  const ctx = setup({ mode: "period" });
  await ctx.ready();
  assert.equal(ctx.controller.selectBattle("Nope"), false);
  assert.equal(ctx.controller.selectedBattle(), null);
  assert.deepEqual(ctx.changes, []);
  assert.equal(ctx.elements["article-split"].classes.has("pane-hidden"), true);
});

test("selectBattle with pickDate sets the date on the timeline page", async () => {
  const ctx = setup({ mode: "date" });
  await ctx.ready();
  ctx.controller.selectBattle("Midway", { pickDate: true });
  assert.deepEqual(ctx.picked, ["1942-06-04"]);
});

test("a link in the article to another battle selects it", async () => {
  const ctx = setup({
    mode: "period",
    loadArticle: async () => ({ html: '<a data-battle="Atlantic" href="#">Atlantic</a>', url: "u" }),
  });
  await ctx.ready();
  clickRow(ctx, "Midway");
  await ctx.ready();
  ctx.elements["article-pane"].byTag("a")[0].dispatch("click");
  assert.equal(ctx.controller.selectedBattle(), "Atlantic");
  assert.equal(articleTitle(ctx), "Atlantic");
  assert.deepEqual(ctx.changes, ["Midway", "Atlantic"]);
});

test("each split leaves the map 320px beside the other", async () => {
  const ctx = setup({ mode: "period", width: 1000 });
  await ctx.ready();
  clickRow(ctx, "Midway");
  const size = (id) => Number(ctx.elements[id].styleProps["--battle-pane-size"].replace("px", ""));
  assert.ok(size("battle-pane") + size("article-pane") <= 1000 - 320);
});

test("onResolved hears whether a deferred selection found its title", async () => {
  const known = setup({ mode: "period" });
  const unknown = setup({ mode: "period" });
  const answers = [];
  known.controller.selectBattle("Midway", { onResolved: (found) => answers.push(["Midway", found]) });
  unknown.controller.selectBattle("Nope", { onResolved: (found) => answers.push(["Nope", found]) });
  assert.deepEqual(answers, []);
  await known.ready();
  await unknown.ready();
  assert.deepEqual(answers, [["Midway", true], ["Nope", false]]);
});

test("moveEditTo moves the square being placed and Bewaar saves that place", async () => {
  const saved = [];
  const { controller, button, squareOf, pans, ready } = await startEditing({ savePosition: async (...args) => saved.push(args) });
  assert.equal(controller.moveEditTo(68.4, 17.4), true);
  assert.deepEqual(squareOf().latlng, [68.4, 17.4]);
  assert.deepEqual(pans.at(-1), [68.4, 17.4]);
  button("battle-edit-save").dispatch("click");
  await ready();
  assert.deepEqual(saved, [["Midway", 68.4, 17.4]]);
});

test("moveEditTo without an edit does nothing and returns false", async () => {
  const { controller, pans, ready } = setup({ mode: "period" });
  await ready();
  assert.equal(controller.moveEditTo(1, 2), false);
  assert.deepEqual(pans, []);
});

test("moveEditTo then Annuleer saves nothing and keeps the old place", async () => {
  const saved = [];
  const { controller, button, squareOf } = await startEditing({ savePosition: async (...args) => saved.push(args) });
  controller.moveEditTo(68.4, 17.4);
  button("battle-edit-cancel").dispatch("click");
  assert.deepEqual(saved, []);
  assert.deepEqual(squareOf().latlng, [30, -178]);
  assert.equal(controller.moveEditTo(1, 2), false);
});

import { test, mock, afterEach } from "node:test";
import assert from "node:assert/strict";

import { createMapSearch } from "../js/map-search.js";
import { Element } from "./battle-dom.js";

afterEach(() => mock.timers.reset());

const NARVIK = { name: "Narvik", sub: "Nordland, Norway", lat: 68.4, lng: 17.4, bbox: [68.3, 68.5, 17.2, 17.6] };

function deferred() {
  const d = {};
  d.promise = new Promise((resolve, reject) => {
    d.resolve = resolve;
    d.reject = reject;
  });
  return d;
}

function setup({ sources, answer = async () => [NARVIK] } = {}) {
  mock.timers.enable(["setTimeout"]);
  const doc = new Element("document");
  doc.createElement = (tag) => new Element(tag);
  const win = { setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout: (id) => clearTimeout(id) };
  const markers = [];
  const calls = [];
  const picks = [];
  const view = [];
  let control;
  globalThis.L = {
    control: (options) => {
      control = { options, addTo(map) { control.el = control.onAdd(map); return control; } };
      return control;
    },
    DomEvent: { disableClickPropagation() {}, disableScrollPropagation() {} },
    marker: (latlng) => {
      const marker = {
        latlng,
        removed: false,
        bindTooltip(content, options) { marker.tooltip = { content, options }; return marker; },
        addTo() { markers.push(marker); return marker; },
        remove() { marker.removed = true; },
      };
      return marker;
    },
  };
  const map = {
    fitBounds: (bounds, options) => view.push(["fitBounds", bounds, options]),
    setView: (center, zoom) => view.push(["setView", center, zoom]),
  };
  const fetchPlaces = (query, options) => {
    calls.push({ query, options });
    return answer(query, options);
  };
  const search = createMapSearch({
    map,
    sources: sources ?? [
      { group: "Boten", search: (q) => (q.toLowerCase().startsWith("n") ? [{ label: "U-1", sub: "Nar", item: { slug: "u1" } }] : []) },
      { group: "Veldslagen", search: (q) => (q.toLowerCase().startsWith("n") ? [{ label: "Narvik 1940", sub: null, item: { title: "Narvik 1940" } }] : []) },
    ],
    onPick: (pick) => picks.push(pick),
    fetchPlaces,
    doc,
    win,
  });
  const input = control.el.byTag("input")[0];
  const type = (text) => {
    input.value = text;
    input.dispatch("input");
  };
  const key = (k, extra = {}) => input.dispatch("keydown", { key: k, stopPropagation() {}, ...extra });
  const rows = () => control.el.byClass("map-search-row");
  const flush = async () => {
    for (let i = 0; i < 5; i++) await Promise.resolve();
  };
  return { search, control, input, type, key, rows, calls, picks, markers, view, doc, flush };
}

const text = (t) => t.control.el.allText();

test("the control sits at topleft", () => {
  const t = setup();
  assert.equal(t.control.options.position, "topleft");
  assert.equal(t.input.getAttribute("placeholder"), "Zoek plaats, boot, schip of veldslag (Ctrl+K)");
});

test("typing shows app groups at once and fetches places once, 400 ms after the last key, from 3 characters", async () => {
  const t = setup();
  t.type("n");
  t.type("na");
  assert.match(text(t), /Boten/);
  assert.match(text(t), /Veldslagen/);
  t.type("nar");
  assert.match(text(t), /Narvik 1940/);
  assert.equal(t.calls.length, 0);
  mock.timers.tick(399);
  assert.equal(t.calls.length, 0);
  mock.timers.tick(1);
  assert.deepEqual(t.calls.map((c) => c.query), ["nar"]);
  await t.flush();
  assert.match(text(t), /Plaatsen/);
  assert.match(text(t), /Nordland, Norway/);
});

test("the Plaatsen group says it is loading while the app groups already show", () => {
  const t = setup({ answer: () => new Promise(() => {}) });
  t.type("nar");
  mock.timers.tick(400);
  assert.match(text(t), /Plaatsen zoeken…/);
  assert.match(text(t), /Narvik 1940/);
});

test("typing again within 400 ms gives one call with the latest text", () => {
  const t = setup();
  t.type("nar");
  mock.timers.tick(300);
  t.type("narv");
  mock.timers.tick(300);
  assert.equal(t.calls.length, 0);
  mock.timers.tick(100);
  assert.deepEqual(t.calls.map((c) => c.query), ["narv"]);
});

test("an older answer that arrives late is ignored and the older request is aborted", async () => {
  const pending = {};
  const t = setup({ answer: (q) => (pending[q] = deferred()).promise });
  t.type("nar");
  mock.timers.tick(400);
  t.type("narv");
  mock.timers.tick(400);
  assert.ok(t.calls[0].options.signal.aborted);
  pending.narv.resolve([{ ...NARVIK, name: "Narvik Newer" }]);
  await t.flush();
  pending.nar.resolve([{ ...NARVIK, name: "Narvik Older" }]);
  await t.flush();
  assert.match(text(t), /Narvik Newer/);
  assert.doesNotMatch(text(t), /Narvik Older/);
});

test("an older rejection does not replace the current answer with an error", async () => {
  const pending = {};
  const t = setup({ answer: (q) => (pending[q] = deferred()).promise });
  t.type("nar");
  mock.timers.tick(400);
  t.type("narv");
  mock.timers.tick(400);
  pending.narv.resolve([NARVIK]);
  await t.flush();
  pending.nar.reject(new Error("aborted"));
  await t.flush();
  assert.doesNotMatch(text(t), /mislukt/);
});

test("clearing the field before 400 ms makes no call and closes the list", () => {
  const t = setup();
  t.type("nar");
  mock.timers.tick(200);
  t.type("");
  mock.timers.tick(1000);
  assert.equal(t.calls.length, 0);
  assert.equal(t.rows().length, 0);
});

test("clearing the field aborts a fetch in flight", () => {
  const t = setup({ answer: () => new Promise(() => {}) });
  t.type("nar");
  mock.timers.tick(400);
  t.type("");
  assert.ok(t.calls[0].options.signal.aborted);
});

test("ArrowDown, ArrowDown, Enter picks the second row", async () => {
  const t = setup();
  t.type("nar");
  mock.timers.tick(400);
  await t.flush();
  t.key("ArrowDown");
  t.key("ArrowDown");
  t.key("Enter");
  assert.deepEqual(t.picks, [{ group: "Veldslagen", item: { title: "Narvik 1940" } }]);
});

test("ArrowUp wraps and clicking a row picks it; places come last under Plaatsen", async () => {
  const t = setup();
  t.type("nar");
  mock.timers.tick(400);
  await t.flush();
  t.key("ArrowUp");
  t.key("Enter");
  assert.deepEqual(t.picks, [{ group: "Plaatsen", item: NARVIK }]);
  assert.equal(t.rows().length, 0);
  t.type("nar");
  t.rows()[0].dispatch("click");
  assert.equal(t.picks[1].group, "Boten");
});

test("Enter with no row chosen fetches places straight away", () => {
  const t = setup();
  t.type("nar");
  t.key("Enter");
  assert.deepEqual(t.calls.map((c) => c.query), ["nar"]);
  mock.timers.tick(1000);
  assert.equal(t.calls.length, 1);
  assert.equal(t.picks.length, 0);
});

test("a rejected fetch says Plaatsen zoeken mislukt. while the app groups stay", async () => {
  const t = setup({ answer: async () => { throw new Error("503"); } });
  t.type("nar");
  mock.timers.tick(400);
  await t.flush();
  assert.match(text(t), /Plaatsen zoeken mislukt\./);
  assert.match(text(t), /Narvik 1940/);
});

test("no result anywhere says Niets gevonden.", async () => {
  const t = setup({ answer: async () => [] });
  t.type("zzz");
  mock.timers.tick(400);
  await t.flush();
  assert.match(text(t), /Niets gevonden\./);
});

test("Niets gevonden. is not shown while places are still loading", () => {
  const t = setup({ answer: () => new Promise(() => {}) });
  t.type("zzz");
  mock.timers.tick(400);
  assert.doesNotMatch(text(t), /Niets gevonden/);
});

test("Esc closes the list, blurs the field and does not bubble", async () => {
  const t = setup();
  t.type("nar");
  t.input.focus();
  let stopped = false;
  t.key("Escape", { stopPropagation: () => (stopped = true) });
  assert.equal(t.rows().length, 0);
  assert.equal(t.input.focused, false);
  assert.ok(stopped);
});

test("Ctrl+K on the document focuses the field even from another input", () => {
  const t = setup();
  const other = new Element("input");
  other.parent = t.doc;
  const event = other.dispatch("keydown", { key: "k", ctrlKey: true });
  assert.ok(event.defaultPrevented);
  assert.equal(t.input.focused, true);
  const mac = t.doc.dispatch("keydown", { key: "K", metaKey: true });
  assert.ok(mac.defaultPrevented);
  const plain = t.doc.dispatch("keydown", { key: "k" });
  assert.ok(!plain.defaultPrevented);
});

test("rows are built from text, never markup", async () => {
  const t = setup({ answer: async () => [{ ...NARVIK, name: "<b>x</b>" }] });
  t.type("nar");
  mock.timers.tick(400);
  await t.flush();
  assert.match(text(t), /<b>x<\/b>/);
});

test("showPlace fits the bbox to at most zoom 10, marks the place and removes the marker after 30 s", () => {
  const t = setup();
  t.search.showPlace(NARVIK);
  assert.deepEqual(t.view[0], ["fitBounds", [[68.3, 17.2], [68.5, 17.6]], { maxZoom: 10 }]);
  assert.deepEqual(t.markers[0].latlng, [68.4, 17.4]);
  assert.equal(t.markers[0].tooltip.content, "Narvik");
  mock.timers.tick(29999);
  assert.equal(t.markers[0].removed, false);
  mock.timers.tick(1);
  assert.equal(t.markers[0].removed, true);
});

test("showPlace without a bbox sets the view to zoom 10; the next showPlace and clear remove the marker", () => {
  const t = setup();
  t.search.showPlace({ ...NARVIK, bbox: null });
  assert.deepEqual(t.view[0], ["setView", [68.4, 17.4], 10]);
  t.search.showPlace(NARVIK);
  assert.equal(t.markers[0].removed, true);
  t.search.clear();
  assert.equal(t.markers[1].removed, true);
  mock.timers.tick(60000);
});

test("Esc in the field removes the temporary marker", () => {
  const t = setup();
  t.search.showPlace(NARVIK);
  t.key("Escape");
  assert.equal(t.markers[0].removed, true);
});

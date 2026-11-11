import { test } from "node:test";
import assert from "node:assert/strict";

import { createLiberationLayer, loadLiberations } from "../js/liberation-layer.js";

class FakeMarker {
  constructor(latlng, options) {
    this.latlng = latlng;
    this.options = options;
    this.handlers = {};
  }

  bindTooltip(text) {
    this.tooltip = text;
  }

  on(type, handler) {
    this.handlers[type] = handler;
    return this;
  }
}

function fakeMap() {
  const panes = {};
  return {
    panes,
    addLayer() {},
    createPane(name) { panes[name] = { style: {} }; },
    getPane: (name) => panes[name],
  };
}

function install() {
  const markers = [];
  const removed = [];
  globalThis.L = {
    svg: (options) => ({ kind: "svg", options }),
    layerGroup: () => ({ addTo() { return this; }, addLayer() {}, removeLayer: (marker) => removed.push(marker) }),
    circleMarker: (latlng, options) => {
      const marker = new FakeMarker(latlng, options);
      markers.push(marker);
      return marker;
    },
  };
  return { markers, removed };
}

const mesch = {
  place: "Mesch", title: "Mesch", lang: "nl", country: "Nederland", liberated: "1944-09-12", verb: "bevrijd",
  by: "Amerikaanse 30e Infanteriedivisie", lat: 50.76, lng: 5.72, source: "nl", name: "Mesch",
};
const item = (state = "liberated", liberation = mesch) => ({ key: "nl|Mesch", liberation, state });

test("liberations lie above the routes and below the ships, in SVG", () => {
  const { markers } = install();
  const map = fakeMap();
  createLiberationLayer(map).setLiberations([item()]);
  assert.equal(map.panes.liberations.style.zIndex, 440);
  assert.equal(markers[0].options.renderer.kind, "svg");
  assert.equal(markers[0].options.renderer.options.pane, "liberations");
  assert.equal(markers[0].options.radius, 4);
  assert.match(markers[0].options.className, /win1-westers/);
  assert.equal(markers[0].tooltip, "Mesch — bevrijd op 12 september 1944 door Amerikaanse 30e Infanteriedivisie");
});

test("a liberation is big enough for a finger on a touch screen", () => {
  const { markers } = install();
  globalThis.matchMedia = () => ({ matches: true });
  try {
    createLiberationLayer(fakeMap()).setLiberations([item()]);
    assert.equal(markers[0].options.radius, 7);
  } finally {
    delete globalThis.matchMedia;
  }
});

test("a place without a position is not drawn", () => {
  const { markers } = install();
  const { lat, lng, ...nowhere } = mesch;
  createLiberationLayer(fakeMap()).setLiberations([item("liberated", nowhere)]);
  assert.equal(markers.length, 0);
});

test("a marker stays while its place keeps its state, and is redrawn when the state changes", () => {
  const { markers, removed } = install();
  const layer = createLiberationLayer(fakeMap());
  layer.setLiberations([item("occupied")]);
  layer.setLiberations([item("occupied")]);
  assert.equal(markers.length, 1);
  layer.setLiberations([item("liberated")]);
  assert.equal(markers.length, 2);
  assert.deepEqual(removed, [markers[0]]);
  assert.equal(markers[1].options.fill, true);
  layer.setLiberations([]);
  assert.deepEqual(removed, [markers[0], markers[1]]);
});

test("clicking reports the newest liberation of that marker", () => {
  const { markers } = install();
  const clicked = [];
  const layer = createLiberationLayer(fakeMap(), { onLiberationClick: (l) => clicked.push(l) });
  layer.setLiberations([item()]);
  const newer = { ...mesch, operation: "Operatie Market Garden" };
  layer.setLiberations([item("liberated", newer)]);
  assert.equal(markers.length, 1);
  markers[0].handlers.click();
  assert.deepEqual(clicked, [newer]);
});

test("switching the liberations off hides their pane", () => {
  install();
  const map = fakeMap();
  const layer = createLiberationLayer(map);
  layer.setVisible(false);
  assert.equal(map.panes.liberations.style.display, "none");
  layer.setVisible(true);
  assert.equal(map.panes.liberations.style.display, "");
});

test("the liberations are read from battles/bevrijdingen.json", async () => {
  const asked = [];
  const records = await loadLiberations(async (url) => {
    asked.push(url);
    return { ok: true, json: async () => [mesch] };
  });
  assert.deepEqual(asked, ["battles/bevrijdingen.json"]);
  assert.deepEqual(records, [mesch]);
  await assert.rejects(loadLiberations(async () => ({ ok: false, status: 404 })));
  await assert.rejects(loadLiberations(async () => ({ ok: true, json: async () => ({}) })));
});

import { test } from "node:test";
import assert from "node:assert/strict";

import { createShipLayer } from "../js/ship-layer.js";

class FakeMarker {
  constructor(latlng, options) {
    this.latlng = latlng;
    this.options = options;
    this.handlers = {};
  }

  bindTooltip() {}

  bringToBack() {}

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
  globalThis.L = {
    svg: (options) => ({ kind: "svg", options }),
    layerGroup: () => ({ addTo() { return this; }, addLayer() {}, removeLayer() {} }),
    circleMarker: (latlng, options) => new FakeMarker(latlng, options),
  };
  const markers = [];
  const make = globalThis.L.circleMarker;
  globalThis.L.circleMarker = (...args) => {
    const marker = make(...args);
    markers.push(marker);
    return marker;
  };
  return markers;
}

const ship = (over = {}) => ({
  ship_external_id: "408", boat_slug: "u99", boat_number: "U-99", name: "Magog", date: "1940-07-05",
  tons: 2053, outcome: "sunk", lat: 50, lng: -11, convoy: null, ...over,
});

test("clicking a ship's marker reports that ship", () => {
  const markers = install();
  const clicked = [];
  const layer = createShipLayer(fakeMap(), { onShipClick: (s) => clicked.push(s) });

  layer.setShips([ship()]);
  markers[0].handlers.click();

  assert.deepEqual(clicked, [ship()]);
});

test("a marker that stays reports the newest data of its ship", () => {
  const markers = install();
  const clicked = [];
  const layer = createShipLayer(fakeMap(), { onShipClick: (s) => clicked.push(s) });

  layer.setShips([ship()]);
  layer.setShips([ship({ convoy: "HX-52" })]);
  markers[0].handlers.click();

  assert.equal(markers.length, 1);
  assert.equal(clicked[0].convoy, "HX-52");
});

test("a layer without a click handler still works", () => {
  const markers = install();
  const layer = createShipLayer(fakeMap());

  layer.setShips([ship()]);

  assert.doesNotThrow(() => markers[0].handlers.click());
});

test("ships lie above the boats and routes and below the Veldslag squares", () => {
  const markers = install();
  const map = fakeMap();
  createShipLayer(map).setShips([ship()]);

  const zIndex = map.panes.ships.style.zIndex;
  assert.ok(zIndex > 400, "above Leaflet's overlay pane, where the boats are");
  assert.ok(zIndex < 600, "below Leaflet's marker pane, where the squares are");
  // SVG lets the mouse through between its shapes; a canvas on top would stop every route and boat.
  assert.equal(markers[0].options.renderer.kind, "svg");
  assert.equal(markers[0].options.renderer.options.pane, "ships");
});

test("a ship is big enough for a finger on a touch screen", () => {
  const markers = install();
  globalThis.matchMedia = () => ({ matches: true });
  try {
    createShipLayer(fakeMap()).setShips([ship()]);
    assert.equal(markers[0].options.radius, 7);
  } finally {
    delete globalThis.matchMedia;
  }
});

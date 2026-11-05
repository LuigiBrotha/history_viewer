import { test } from "node:test";
import assert from "node:assert/strict";

import { createShipLayer } from "../js/ship-layer.js";

class FakeMarker {
  constructor(latlng) {
    this.latlng = latlng;
    this.handlers = {};
  }

  bindTooltip() {}

  bringToBack() {}

  on(type, handler) {
    this.handlers[type] = handler;
    return this;
  }
}

class FakeCanvas {
  addTo() {
    return this;
  }
}

function install() {
  globalThis.L = {
    Canvas: FakeCanvas,
    canvas: () => new FakeCanvas(),
    layerGroup: () => ({ addTo() { return this; }, addLayer() {}, removeLayer() {} }),
    circleMarker: (latlng) => new FakeMarker(latlng),
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
  const layer = createShipLayer({ options: {}, addLayer() {} }, { onShipClick: (s) => clicked.push(s) });

  layer.setShips([ship()]);
  markers[0].handlers.click();

  assert.deepEqual(clicked, [ship()]);
});

test("a marker that stays reports the newest data of its ship", () => {
  const markers = install();
  const clicked = [];
  const layer = createShipLayer({ options: {}, addLayer() {} }, { onShipClick: (s) => clicked.push(s) });

  layer.setShips([ship()]);
  layer.setShips([ship({ convoy: "HX-52" })]);
  markers[0].handlers.click();

  assert.equal(markers.length, 1);
  assert.equal(clicked[0].convoy, "HX-52");
});

test("a layer without a click handler still works", () => {
  const markers = install();
  const layer = createShipLayer({ options: {}, addLayer() {} });

  layer.setShips([ship()]);

  assert.doesNotThrow(() => markers[0].handlers.click());
});

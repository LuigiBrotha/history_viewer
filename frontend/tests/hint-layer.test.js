import { test } from "node:test";
import assert from "node:assert/strict";

import { createHintLayer, hintBounds } from "../js/hint-layer.js";
import { installDom } from "./battle-dom.js";

test("hintBounds spans all hints", () => {
  assert.deepEqual(hintBounds([{ lat: 31.6, lng: 23.5 }, { lat: 32.1, lng: 22.9 }]), [[31.6, 22.9], [32.1, 23.5]]);
});

test("show draws a ring per hint by kind, fits the map to them and reports a click; clear removes them", () => {
  installDom();
  const layers = new Set();
  const fits = [];
  globalThis.L = {
    layerGroup: () => ({ addTo() { return this; }, addLayer: (l) => layers.add(l), removeLayer: (l) => layers.delete(l) }),
    divIcon: (options) => options,
    marker: (latlng, options) => {
      const marker = { latlng, options, events: {}, on(type, fn) { marker.events[type] = fn; return marker; } };
      return marker;
    },
  };
  const picked = [];
  const layer = createHintLayer({ fitBounds: (bounds, options) => fits.push([bounds, options]) }, { onPick: (h) => picked.push(h.name) });
  layer.show([{ name: "Bir Hakeim", lat: 31.6, lng: 23.5, kind: "infobox" }, { name: "Tobruk", lat: 32.1, lng: 23.9, kind: "artikel" }]);
  const markers = [...layers];
  assert.deepEqual(markers.map((m) => m.options.icon.className), ["place-hint infobox", "place-hint artikel"]);
  assert.equal(markers[0].options.icon.html.byClass("place-hint-name")[0].textContent, "Bir Hakeim");
  assert.equal(markers[0].options.icon.html.byClass("place-hint-triangle").length, 1);
  assert.deepEqual(fits, [[[[31.6, 23.5], [32.1, 23.9]], { maxZoom: 8, padding: [48, 48] }]]);
  markers[1].events.click();
  assert.deepEqual(picked, ["Tobruk"]);
  layer.show([]);
  assert.equal(layers.size, 0);
  assert.equal(fits.length, 1);
  layer.show([{ name: "Gazala", lat: 32.1, lng: 23.1, kind: "artikel" }], { fit: false });
  assert.equal(layers.size, 1);
  assert.equal(fits.length, 1);
  layer.show([{ name: "X", lat: 1, lng: 2, kind: "artikel" }]);
  layer.clear();
  assert.equal(layers.size, 0);
});

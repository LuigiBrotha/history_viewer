import { test } from "node:test";
import assert from "node:assert/strict";

import { NUMBER_ANCHOR, TRACK_COLORS, createTrackLayer, trackColor, trackSegments } from "../js/track-layer.js";

test("trackSegments puts an arrow halfway each step, pointing the way the track goes", () => {
  const [east, north] = trackSegments([{ lat: 0, lng: 0 }, { lat: 0, lng: 10 }, { lat: 10, lng: 10 }]);
  assert.deepEqual(east.mid, [0, 5]);
  assert.equal(Math.round(east.angle), 0);
  assert.equal(east.mid.length, 2);
  assert.ok(Math.abs(north.angle - -90) < 1);
  assert.deepEqual(trackSegments([{ lat: 1, lng: 1 }]), []);
});

function fakeLeaflet() {
  const added = [];
  const group = {
    addTo() { return this; },
    addLayer(layer) { added.push(layer); },
    removeLayer(layer) { added.splice(added.indexOf(layer), 1); },
  };
  globalThis.L = {
    layerGroup: () => group,
    polyline: (latlngs, options) => ({ kind: "line", latlngs, options }),
    marker: (latlng, options) => ({ kind: "marker", latlng, options }),
    divIcon: (options) => options,
  };
  globalThis.document = {
    createElement: (tag) => ({ tag, style: {}, className: "", textContent: "" }),
  };
  return added;
}

test("each track is a coloured line with an arrow per step and a number per battle", () => {
  const added = fakeLeaflet();
  const layer = createTrackLayer({});
  layer.setTracks([
    { battles: [{ lat: 0, lng: 0, title: "A" }, { lat: 0, lng: 10, title: "B" }], color: TRACK_COLORS[0] },
    { battles: [{ lat: 5, lng: 5, title: "C" }], color: TRACK_COLORS[1] },
  ]);
  const lines = added.filter((l) => l.kind === "line");
  assert.equal(lines.length, 1);
  assert.equal(lines[0].options.color, TRACK_COLORS[0]);
  const icons = added.filter((l) => l.kind === "marker").map((m) => m.options.icon.className);
  assert.deepEqual(icons.sort(), ["track-arrow", "track-number", "track-number", "track-number"]);
  const numbers = added.filter((l) => l.kind === "marker" && l.options.icon.className === "track-number")
    .map((m) => m.options.icon.html.textContent);
  assert.deepEqual(numbers, ["1", "2", "1"]);
  // The numbers sit beside the square, above it and above the squares drawn later.
  const number = added.find((l) => l.kind === "marker" && l.options.icon.className === "track-number");
  assert.ok(number.options.zIndexOffset >= 1000);
  assert.deepEqual(number.options.icon.iconAnchor, [NUMBER_ANCHOR, NUMBER_ANCHOR]);
  layer.setTracks([]);
  assert.equal(added.length, 0);
});

test("trackColor gives each Spoor label the colour of its line, in label order; other labels none", () => {
  const labels = [
    { kind: "land", value: "Polen" },
    { kind: "bevelhebber", value: "Erwin Rommel" },
    { kind: "eenheid", value: "7th Panzer Division" },
  ];
  assert.equal(trackColor(labels, labels[0]), null);
  assert.equal(trackColor(labels, labels[1]), TRACK_COLORS[0]);
  assert.equal(trackColor(labels, { kind: "eenheid", value: "7th Panzer Division" }), TRACK_COLORS[1]);
});

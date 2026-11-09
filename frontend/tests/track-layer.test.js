import { test } from "node:test";
import assert from "node:assert/strict";

import { NUMBER_ANCHOR, TRACK_COLORS, createTrackLayer, trackColor, trackName, trackSegments } from "../js/track-layer.js";

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
  const hoverable = (layer) => Object.assign(layer, {
    events: {},
    styles: [],
    tooltip: null,
    on(handlers) { Object.assign(layer.events, handlers); return layer; },
    bindTooltip(content, options) { layer.tooltip = { content, options }; return layer; },
    setStyle(style) { layer.styles.push(style); return layer; },
    bringToFront() { layer.front = true; return layer; },
    setOpacity(value) { layer.opacity = value; return layer; },
  });
  globalThis.L = {
    layerGroup: () => group,
    polyline: (latlngs, options) => hoverable({ kind: "line", latlngs, options }),
    marker: (latlng, options) => hoverable({ kind: "marker", latlng, options }),
    divIcon: (options) => options,
  };
  globalThis.document = {
    createElement: (tag) => ({ tag, style: {}, className: "", textContent: "" }),
  };
  return added;
}

test("there are twelve different Spoor colours, repeating after that", () => {
  assert.equal(new Set(TRACK_COLORS).size, 12);
  const labels = Array.from({ length: 13 }, (_, i) => ({ kind: "bevelhebber", value: `P${i}` }));
  assert.equal(trackColor(labels, labels[11]), TRACK_COLORS[11]);
  assert.equal(trackColor(labels, labels[12]), TRACK_COLORS[0]);
});

test("the name of a Bevelhebber is his Wikipedia title without what is between brackets", () => {
  assert.equal(trackName("Kenneth Anderson (British Army officer)"), "Kenneth Anderson");
  assert.equal(trackName("Erwin Rommel"), "Erwin Rommel");
});

const two = (a, b) => [{ lat: 0, lng: a, title: "A" }, { lat: 0, lng: b, title: "B" }];
const lines = (added) => added.filter((l) => l.kind === "line" && l.options.className !== "track-hit");
const hits = (added) => added.filter((l) => l.options.className === "track-hit");
const names = (added) => added.filter((l) => l.kind === "marker" && l.options.icon.className === "track-name");

test("a named track shows its name at its last battle, in its colour", () => {
  const added = fakeLeaflet();
  createTrackLayer({}).setTracks([{ battles: two(0, 10), color: "#111111", name: "John Frost (British Army officer)" }]);
  const [label] = names(added);
  assert.deepEqual(label.latlng, [0, 10]);
  assert.equal(label.options.icon.html.textContent, "John Frost");
  assert.equal(label.options.icon.html.style.color, "#111111");
  assert.equal(label.options.interactive, false);
});

test("a named track of one battle has no line, so no name on the map", () => {
  const added = fakeLeaflet();
  createTrackLayer({}).setTracks([{ battles: [{ lat: 1, lng: 2, title: "A" }], color: "red", name: "X" }]);
  assert.equal(names(added).length, 0);
  assert.equal(hits(added).length, 0);
});

test("hovering a track lights it up with a tooltip and dims the others, leaving restores them", () => {
  const added = fakeLeaflet();
  createTrackLayer({}).setTracks([
    { battles: two(0, 10), color: "red", name: "Anna (x)" },
    { battles: two(20, 30), color: "blue", name: "Bert" },
  ]);
  const [hitA] = hits(added);
  const [lineA, lineB] = lines(added);
  assert.equal(hitA.tooltip.content.textContent, "Anna");
  assert.equal(hitA.tooltip.options.sticky, true);
  assert.equal(hitA.options.interactive, undefined);
  hitA.events.mouseover();
  assert.deepEqual(lineA.styles.at(-1), { weight: 6, opacity: 1 });
  assert.equal(lineA.front, true);
  assert.deepEqual(lineB.styles.at(-1), { weight: 3, opacity: 0.2 });
  const [nameA, nameB] = names(added);
  assert.equal(nameA.opacity, 1);
  assert.equal(nameB.opacity, 0.2);
  hitA.events.mouseout();
  assert.deepEqual(lineA.styles.at(-1), { weight: 3, opacity: 0.9 });
  assert.deepEqual(lineB.styles.at(-1), { weight: 3, opacity: 0.9 });
  assert.equal(nameB.opacity, 1);
});

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

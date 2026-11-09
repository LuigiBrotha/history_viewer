import { test } from "node:test";
import assert from "node:assert/strict";

import { bandPolygon, createManpowerLayer, lossWedge } from "../js/manpower-layer.js";

test("bandPolygon runs from the width of one end to the width of the other", () => {
  const [p1, p2, p3, p4] = bandPolygon({ x: 0, y: 0 }, { x: 10, y: 0 }, 4, 8);
  assert.deepEqual([p1, p2, p3, p4].map((p) => [p.x + 0, p.y + 0]), [[0, 2], [10, 4], [10, -4], [0, -2]]);
});

test("two battles on the same spot draw no polygon", () =>
  assert.equal(bandPolygon({ x: 1, y: 1 }, { x: 1, y: 1 }, 4, 8), null));

test("a wedge sits on the left edge, 12 px along the band, and is never deeper than the band", () => {
  const point = { x: 0, y: 0 };
  const tangent = { x: 1, y: 0 };
  const [a, b, apex] = lossWedge(point, tangent, 10, 4);
  assert.deepEqual([a, b].map((p) => [p.x + 0, p.y + 0]), [[-6, 5], [6, 5]]);
  assert.deepEqual([apex.x + 0, apex.y + 0], [0, 1]);
  assert.equal(lossWedge(point, tangent, 10, 99)[2].y, -5);
  assert.equal(lossWedge(point, tangent, 10, 0.2)[2].y, 4);
});

function fakeLeaflet() {
  const added = [];
  const panes = {};
  const handlers = {};
  const group = {
    addTo() { return this; },
    addLayer(layer) { added.push(layer); },
    removeLayer(layer) { added.splice(added.indexOf(layer), 1); },
  };
  const shape = (kind) => (latlngs, options) => {
    const layer = { kind, latlngs, options, tooltip: null, bindTooltip(content, o) { layer.tooltip = { content, options: o }; return layer; } };
    return layer;
  };
  globalThis.L = {
    layerGroup: () => group,
    polygon: shape("polygon"),
    polyline: shape("polyline"),
    circleMarker: shape("circle"),
  };
  globalThis.document = { createElement: (tag) => ({ tag, className: "", textContent: "" }) };
  const map = {
    scale: 1,
    createPane(name) { panes[name] = { style: {} }; return panes[name]; },
    getPane: (name) => panes[name],
    on(type, fn) { handlers[type] = fn; },
    latLngToLayerPoint: ([lat, lng]) => ({ x: lng * map.scale, y: -lat * map.scale }),
    layerPointToLatLng: (p) => [-p.y / map.scale, p.x / map.scale],
  };
  return { added, panes, handlers, map };
}

const battle = (title, lat, lng) => ({ title, lat, lng });
const stop = (title, lng, total, loss = null) => ({
  battle: battle(title, 0, lng),
  manpower: total == null ? null : { total, soldiers: total, tanks: 0, aircraft: 0, borrowedFrom: null },
  loss,
  entry: total == null ? null : {},
});
const of = (added, kind) => added.filter((l) => l.kind === kind);

test("panes lie under the Spoor, the band half transparent so overlaps do not darken", () => {
  const { panes, map } = fakeLeaflet();
  createManpowerLayer(map);
  assert.equal(panes.manpower.style.zIndex, 395);
  assert.equal(panes.manpower.style.opacity, 0.55);
  assert.equal(panes["manpower-losses"].style.zIndex, 396);
});

test("a step with figures at both ends is a polygon in the Spoor colour, a circle closes each end", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 50), stop("B", 10, 100)], color: "#6b2fbf" }]);
  assert.equal(layer.highest(), 100);
  assert.equal(layer.maxWidth(), 48);
  const polygons = of(added, "polygon").filter((p) => p.options.pane === "manpower");
  assert.equal(polygons.length, 1);
  assert.equal(polygons[0].options.fillColor, "#6b2fbf");
  assert.equal(polygons[0].options.stroke, false);
  assert.equal(polygons[0].tooltip.options.sticky, true);
  assert.equal(polygons[0].tooltip.content.textContent.split("\n\n").length, 2);
  assert.deepEqual(of(added, "circle").map((c) => c.options.radius), [12, 24]);
});

test("a step without figures is dashed and a battle without a band has no wedge", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 50, 10), stop("B", 10, null, 5), stop("C", 20, 100)], color: "red" }]);
  const lines = of(added, "polyline");
  assert.equal(lines.length, 2);
  assert.equal(lines[0].options.dashArray, "4 6");
  assert.equal(lines[0].options.weight, 2);
  assert.equal(of(added, "polygon").filter((p) => p.options.pane === "manpower").length, 0);
  // Only A has a figure and a loss; B has a loss but no band.
  assert.equal(of(added, "polygon").filter((p) => p.options.pane === "manpower-losses").length, 1);
  assert.equal(of(added, "circle").length, 2);
});

test("a loss is drawn as a dark wedge of the same scale, tooltip showing its stop", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100, 25), stop("B", 10, 100)], color: "red" }]);
  const [wedge] = of(added, "polygon").filter((p) => p.options.pane === "manpower-losses");
  assert.equal(wedge.options.fillColor, "#2a2521");
  assert.equal(wedge.latlngs.length, 3);
  assert.equal(wedge.tooltip.content.textContent.split("\n")[0], "A");
});

test("a lone stop draws its circle and, having no direction, no wedge", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100, 25)], color: "red" }]);
  assert.equal(of(added, "circle").length, 1);
  assert.equal(of(added, "polygon").length, 0);
});

test("the width follows the slider and every part is redrawn on zoom", () => {
  const { added, handlers, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100), stop("B", 10, 100)], color: "red" }]);
  layer.setMaxWidth(20);
  assert.equal(layer.maxWidth(), 20);
  assert.deepEqual(of(added, "circle").map((c) => c.options.radius), [10, 10]);
  map.scale = 2;
  handlers.zoomend();
  const p = of(added, "polygon")[0];
  assert.deepEqual(p.latlngs.map((q) => q[1]), [0, 10, 10, 0]);
  assert.equal(of(added, "circle").length, 2);
});

test("setBands([]) removes everything", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100, 5), stop("B", 10, 100)], color: "red" }]);
  assert.ok(added.length > 0);
  layer.setBands([]);
  assert.equal(added.length, 0);
  assert.equal(layer.highest(), 0);
});

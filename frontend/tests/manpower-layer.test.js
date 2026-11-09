import { test } from "node:test";
import assert from "node:assert/strict";

import { bandPolygon, clampBandWidth, createManpowerLayer, lossWedge, scaleBar } from "../js/manpower-layer.js";

test("bandPolygon runs from the width of one end to the width of the other", () => {
  const [p1, p2, p3, p4] = bandPolygon({ x: 0, y: 0 }, { x: 10, y: 0 }, 4, 8);
  assert.deepEqual([p1, p2, p3, p4].map((p) => [p.x + 0, p.y + 0]), [[0, 2], [10, 4], [10, -4], [0, -2]]);
});

test("two battles on the same spot draw no polygon", () =>
  assert.equal(bandPolygon({ x: 1, y: 1 }, { x: 1, y: 1 }, 4, 8), null));

test("a wedge sits on the edge that looks left on screen (north when heading east), 12 px along the band, and is never deeper than the band", () => {
  const point = { x: 0, y: 0 };
  const tangent = { x: 1, y: 0 };
  const [a, b, apex] = lossWedge(point, tangent, 10, 4);
  assert.deepEqual([a, b].map((p) => [p.x + 0, p.y + 0]), [[-6, -5], [6, -5]]);
  assert.deepEqual([apex.x + 0, apex.y + 0], [0, -1]);
  assert.equal(lossWedge(point, tangent, 10, 99)[2].y, 5);
  assert.equal(lossWedge(point, tangent, 10, 0.2)[2].y, -4);
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
  const element = (tag) => {
    const el = { tag, className: "", textContent: "", style: {}, children: [], listeners: {},
      append(...nodes) { el.children.push(...nodes); },
      addEventListener(type, fn) { el.listeners[type] = fn; } };
    return el;
  };
  const controls = [];
  globalThis.L.control = (options) => {
    const control = { options, onMap: null,
      addTo(m) { control.onMap = m; control.element ??= control.onAdd(m); controls.push(control); return control; },
      remove() { control.onMap = null; controls.splice(controls.indexOf(control), 1); return control; } };
    return control;
  };
  globalThis.L.DomUtil = { create: (tag, className) => Object.assign(element(tag), { className }) };
  globalThis.L.DomEvent = { disableClickPropagation(el) { el.clickDisabled = true; } };
  globalThis.document = { createElement: (tag) => element(tag) };
  const map = {
    scale: 1,
    createPane(name) { panes[name] = { style: {} }; return panes[name]; },
    getPane: (name) => panes[name],
    on(type, fn) { handlers[type] = fn; },
    latLngToLayerPoint: ([lat, lng]) => ({ x: lng * map.scale, y: -lat * map.scale }),
    layerPointToLatLng: (p) => [-p.y / map.scale, p.x / map.scale],
  };
  return { added, panes, handlers, map, controls };
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
  const before = of(added, "polygon")[0];
  assert.deepEqual(before.latlngs.map((q) => q[0] + 0), [-10, -10, 10, 10]);
  const countBefore = added.length;
  map.scale = 2;
  handlers.zoomend();
  const after = of(added, "polygon")[0];
  assert.notEqual(after, before);
  assert.ok(!added.includes(before));
  assert.equal(added.length, countBefore);
  // The band is 20 px wide at every zoom, so its edges lie half as far away in degrees.
  assert.deepEqual(after.latlngs.map((q) => q[0] + 0), [-5, -5, 5, 5]);
});

test("setting the same bands twice leaves the same number of layers", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  const bands = [{ stops: [stop("A", 0, 100, 5), stop("B", 10, 100)], color: "red" }];
  layer.setBands(bands);
  const count = added.length;
  assert.ok(count > 0);
  layer.setBands(bands);
  assert.equal(added.length, count);
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

const texts = (el) => [el.textContent, ...el.children.flatMap((c) => (typeof c === "string" ? [c] : texts(c)))];
const find = (el, tag) => (el.tag === tag ? el : el.children.map((c) => (typeof c === "string" ? null : find(c, tag))).find(Boolean));
const twoStops = [{ stops: [stop("A", 0, 100), stop("B", 10, 100)], color: "red" }];

test("clampBandWidth accepts whole numbers from 8 to 96 and nothing else", () => {
  assert.equal(clampBandWidth(48), 48);
  assert.equal(clampBandWidth("64"), 64);
  assert.equal(clampBandWidth(8), 8);
  assert.equal(clampBandWidth(96), 96);
  for (const bad of [0, 7, 97, 9999, "0", "9999", "abc", "", null, undefined, 12.5, "12.5", NaN])
    assert.equal(clampBandWidth(bad), undefined, String(bad));
});

test("the scale bar shows 50.000 Manschappen on the scale of the band", () => {
  const bar = scaleBar(162646, 48);
  assert.equal(bar.men, 50000);
  assert.ok(Math.abs(bar.px - 14.756) < 0.001);
});

test("the slider and the legend only show while there is a band, and are added once", () => {
  const { controls, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  assert.equal(controls.length, 0);
  layer.setBands(twoStops);
  layer.setBands(twoStops);
  assert.equal(controls.length, 1);
  assert.equal(controls[0].options.position, "bottomleft");
  const all = texts(controls[0].element);
  assert.ok(all.includes("Dikte band"));
  assert.ok(all.includes("50.000 Manschappen"));
  assert.ok(all.includes("Cijfer per kant, niet per Bevelhebber"));
  assert.equal(controls[0].element.clickDisabled, true);
  layer.setBands([]);
  assert.equal(controls.length, 0);
  layer.setBands(twoStops);
  assert.equal(controls.length, 1);
});

test("moving the slider sets the width and reports it; the URL sets it silently", () => {
  const { controls, added, map } = fakeLeaflet();
  const reported = [];
  const layer = createManpowerLayer(map, { onWidthChange: (px) => reported.push(px) });
  layer.setBands(twoStops);
  const input = find(controls[0].element, "input");
  assert.equal(input.type, "range");
  assert.deepEqual([input.min, input.max, input.step, input.value], [8, 96, 1, 48]);
  input.value = "20";
  input.listeners.input();
  assert.equal(layer.maxWidth(), 20);
  assert.deepEqual(reported, [20]);
  assert.deepEqual(of(added, "circle").map((c) => c.options.radius), [10, 10]);
  layer.setMaxWidth(64);
  assert.deepEqual(reported, [20]);
  assert.equal(String(input.value), "64");
});

test("the scale bar follows the slider and the highest figure, and is left out without a figure", () => {
  const { controls, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 162646), stop("B", 10, 100)], color: "red" }]);
  const bar = controls[0].element.bar;
  assert.ok(Math.abs(parseFloat(bar.style.width) - 14.756) < 0.001);
  layer.setMaxWidth(96);
  assert.ok(Math.abs(parseFloat(bar.style.width) - 29.512) < 0.001);
  layer.setBands([{ stops: [stop("A", 0, null), stop("B", 10, null)], color: "red" }]);
  assert.equal(controls.length, 1);
  assert.equal(bar.style.display, "none");
});

import { test } from "node:test";
import assert from "node:assert/strict";

import { stopText } from "../js/manpower.js";
import { bandPolygon, createManpowerLayer, hitAt, joinAt, lossWedge, scaleBar } from "../js/manpower-layer.js";

test("bandPolygon runs from the width of one end to the width of the other", () => {
  const [p1, p2, p3, p4] = bandPolygon({ x: 0, y: 0 }, { x: 10, y: 0 }, 4, 8);
  assert.deepEqual([p1, p2, p3, p4].map((p) => [p.x + 0, p.y + 0]), [[0, 2], [10, 4], [10, -4], [0, -2]]);
});

test("a corner is mitred: both sides of the band meet in a sharp point", () => {
  const { plus, minus } = joinAt({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }, 10);
  assert.ok(Math.abs(plus.x - -5) < 1e-9 && Math.abs(plus.y - 5) < 1e-9);
  assert.ok(Math.abs(minus.x - 5) < 1e-9 && Math.abs(minus.y - -5) < 1e-9);
});

test("a straight line goes on with no corner and a near reversal gets no mitre", () => {
  const straight = joinAt({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 0 }, 10);
  assert.ok(Math.abs(straight.plus.y - 5) < 1e-9 && Math.abs(straight.plus.x) < 1e-9);
  assert.equal(joinAt({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: -0.99875, y: 0.04994 }, 10), null);
  assert.equal(joinAt({ x: 0, y: 0 }, { x: 1, y: 0 }, { x: -1, y: 0 }, 10), null);
});

test("bandPolygon takes the corner of a join instead of its own", () => {
  const start = { plus: { x: 1, y: 2 }, minus: { x: 3, y: -2 } };
  const end = { plus: { x: 9, y: 4 }, minus: { x: 7, y: -4 } };
  assert.deepEqual(bandPolygon({ x: 0, y: 0 }, { x: 10, y: 0 }, 4, 8, start, end),
    [start.plus, end.plus, end.minus, start.minus]);
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
  const counts = {};
  const group = {
    addTo() { return this; },
    addLayer(layer) { added.push(layer); },
    removeLayer(layer) { added.splice(added.indexOf(layer), 1); },
  };
  const shape = (kind) => (latlngs, options) => {
    const layer = { kind, latlngs, options };
    return layer;
  };
  const tooltips = [];
  globalThis.L = {
    tooltip(options) {
      const tooltip = { options, content: null, latlng: null, open: false, opened: 0,
        setContent(c) { tooltip.content = c; return tooltip; },
        setLatLng(ll) { tooltip.latlng = ll; return tooltip; },
        addTo() { tooltip.open = true; tooltip.opened += 1; return tooltip; },
        remove() { tooltip.open = false; return tooltip; } };
      tooltips.push(tooltip);
      return tooltip;
    },
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
  globalThis.L.DomEvent = { disableClickPropagation(el) { el.clickDisabled = true; }, disableScrollPropagation(el) { el.scrollDisabled = true; } };
  globalThis.document = { createElement: (tag) => element(tag) };
  const map = {
    scale: 1,
    createPane(name) { panes[name] = { style: {} }; return panes[name]; },
    getPane: (name) => panes[name],
    on(type, fn) { (counts[type] = (counts[type] || 0) + 1); handlers[type] = fn; },
    latLngToLayerPoint: ([lat, lng]) => ({ x: lng * map.scale, y: -lat * map.scale }),
    layerPointToLatLng: (p) => [-p.y / map.scale, p.x / map.scale],
  };
  return { added, panes, handlers, counts, tooltips, map, controls };
}

const battle = (title, lat, lng) => ({ title, lat, lng });
const stop = (title, lng, total, loss = null) => ({
  battle: battle(title, 0, lng),
  manpower: total == null ? null : { total, soldiers: total, tanks: 0, aircraft: 0, borrowedFrom: null },
  loss,
  entry: total == null ? null : {},
});
const of = (added, kind) => added.filter((l) => l.kind === kind);

test("panes lie under the routes, the band half transparent so overlaps do not darken", () => {
  const { panes, map } = fakeLeaflet();
  createManpowerLayer(map);
  assert.equal(panes.manpower.style.zIndex, 385);
  assert.equal(panes.manpower.style.opacity, 0.55);
  assert.equal(panes["manpower-losses"].style.zIndex, 386);
});

test("a step with figures at both ends is a flat-ended polygon in the Spoor colour, with no round parts", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 50), stop("B", 10, 100)], color: "#6b2fbf" }]);
  assert.equal(layer.highest(), 100);
  assert.equal(layer.maxWidth(), 48);
  const polygons = of(added, "polygon").filter((p) => p.options.pane === "manpower");
  assert.equal(polygons.length, 1);
  assert.equal(polygons[0].options.fillColor, "#6b2fbf");
  assert.equal(polygons[0].options.stroke, false);
  assert.equal(polygons[0].options.interactive, false);
  assert.equal(of(added, "circle").length, 0);
});

test("a step without figures is dashed and a battle without a band has no wedge", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 50, 10), stop("B", 10, null, 5), stop("C", 20, 100)], color: "red" }]);
  const lines = of(added, "polyline");
  assert.equal(lines.length, 2);
  assert.equal(lines[0].options.dashArray, "1 7");
  assert.equal(lines[0].options.weight, 2);
  assert.equal(lines[0].options.lineCap, "round");
  // Above the half-transparent band pane, so the fine dots stay crisp.
  assert.equal(lines[0].options.pane, "manpower-losses");
  assert.equal(lines[0].options.interactive, false);
  // A and C have no solid step: each is a short rectangle across the line.
  assert.equal(of(added, "polygon").filter((p) => p.options.pane === "manpower" && p.latlngs.length === 4).length, 2);
  // Only A has a figure and a loss; B has a loss but no band.
  assert.equal(of(added, "polygon").filter((p) => p.options.pane === "manpower-losses").length, 1);
  assert.equal(of(added, "circle").length, 0);
});

test("no part of the band is thinner than 4 px, however small its share", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 1), stop("B", 10, 1000000)], color: "red" }]);
  const [band] = of(added, "polygon");
  assert.deepEqual(band.latlngs.slice(0, 1).concat(band.latlngs.slice(3)).map((q) => q[0] + 0).sort((a, b) => a - b), [-2, 2]);
});

test("a loss is drawn as a dark wedge of the same scale", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100, 25), stop("B", 10, 100)], color: "red" }]);
  const [wedge] = of(added, "polygon").filter((p) => p.options.pane === "manpower-losses");
  assert.equal(wedge.options.fillColor, "#2a2521");
  assert.equal(wedge.latlngs.length, 3);
  assert.equal(wedge.options.interactive, false);
});

test("a lone stop draws a rectangle as wide as its figure, 12 px long, and without direction no wedge", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100, 25)], color: "red" }]);
  assert.equal(of(added, "circle").length, 0);
  const [box, ...rest] = of(added, "polygon");
  assert.equal(rest.length, 0);
  assert.equal(box.options.pane, "manpower");
  const lats = box.latlngs.map((q) => q[0]);
  const lngs = box.latlngs.map((q) => q[1]);
  assert.equal(Math.max(...lngs) - Math.min(...lngs), 12);
  assert.equal(Math.max(...lats) - Math.min(...lats), 48);
});

const at = (title, lat, lng, total) => ({ ...stop(title, lng, total), battle: battle(title, lat, lng) });

test("at a corner the two parts of the band share their outer points, so no gap and no round", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [at("A", 0, 0, 100), at("B", 0, 100, 100), at("C", 100, 100, 100)], color: "red" }]);
  const [first, second] = of(added, "polygon");
  assert.deepEqual(first.latlngs[1], second.latlngs[0]);
  assert.deepEqual(first.latlngs[2], second.latlngs[3]);
  assert.equal(of(added, "circle").length, 0);
});

test("a sharp turn back is closed by two straight triangles instead of a long spike", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [at("A", 0, 0, 100), at("B", 0, 100, 100), at("C", 5, 0, 100)], color: "red" }]);
  const band = of(added, "polygon").filter((p) => p.options.pane === "manpower");
  assert.equal(band.filter((p) => p.latlngs.length === 4).length, 2);
  assert.equal(band.filter((p) => p.latlngs.length === 3).length, 2);
});

test("the width follows the slider and every part is redrawn on zoom", () => {
  const { added, handlers, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100), stop("B", 10, 100)], color: "red" }]);
  layer.setMaxWidth(20);
  assert.equal(layer.maxWidth(), 20);
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
  assert.equal(controls[0].element.scrollDisabled, true);
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
  assert.deepEqual(of(added, "polygon")[0].latlngs.map((q) => q[0] + 0), [-10, -10, 10, 10]);
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

test("no band part is interactive and none carries a tooltip of its own", () => {
  const { added, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 50, 10), stop("B", 10, 100), stop("C", 20, null), stop("D", 30, 80)], color: "red" }]);
  assert.ok(added.length >= 5);
  for (const part of added) {
    assert.equal(part.options.interactive, false, part.kind);
    assert.equal(part.bindTooltip, undefined);
  }
});

const A = { id: "A" };
const B = { id: "B" };
const square = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }];

test("hitAt finds a wedge, a box and a polygon by being inside, and nothing outside", () => {
  const wedge = { kind: "wedge", points: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 5, y: 8 }], stop: A };
  assert.equal(hitAt({ x: 5, y: 2 }, [wedge]), A);
  assert.equal(hitAt({ x: 1, y: 7 }, [wedge]), null);
  const box = { kind: "box", points: [{ x: 45, y: 45 }, { x: 55, y: 45 }, { x: 55, y: 55 }, { x: 45, y: 55 }], stop: B };
  assert.equal(hitAt({ x: 53, y: 53 }, [box]), B);
  assert.equal(hitAt({ x: 56, y: 53 }, [box]), null);
  const polygon = { kind: "polygon", points: square, from: { point: { x: 0, y: 5 }, stop: A }, to: { point: { x: 10, y: 5 }, stop: B } };
  assert.ok(hitAt({ x: 5, y: 5 }, [polygon]));
  assert.equal(hitAt({ x: 11, y: 5 }, [polygon]), null);
});

test("hitAt gives a wedge priority over what lies beneath it, in list order", () => {
  const wedge = { kind: "wedge", points: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 5, y: 8 }], stop: A };
  const polygon = { kind: "polygon", points: square, from: { point: { x: 0, y: 5 }, stop: B }, to: { point: { x: 10, y: 5 }, stop: B } };
  assert.equal(hitAt({ x: 5, y: 2 }, [wedge, polygon]), A);
  assert.equal(hitAt({ x: 5, y: 2 }, [polygon, wedge]), B);
});

test("hitAt reports the nearer of the two stops of a polygon", () => {
  const polygon = { kind: "polygon", points: square, from: { point: { x: 0, y: 5 }, stop: A }, to: { point: { x: 10, y: 5 }, stop: B } };
  assert.equal(hitAt({ x: 2, y: 5 }, [polygon]), A);
  assert.equal(hitAt({ x: 8, y: 1 }, [polygon]), B);
});

test("hitAt hits a dotted step within 8 px of its segment and reports the nearer stop", () => {
  const step = { kind: "step", from: { point: { x: 0, y: 0 }, stop: A }, to: { point: { x: 100, y: 0 }, stop: B } };
  assert.equal(hitAt({ x: 30, y: 8 }, [step]), A);
  assert.equal(hitAt({ x: 70, y: -8 }, [step]), B);
  assert.equal(hitAt({ x: 30, y: 8.5 }, [step]), null);
  assert.equal(hitAt({ x: 108, y: 0 }, [step]), B);
  assert.equal(hitAt({ x: 109, y: 0 }, [step]), null);
});

test("hitAt without shapes or without a hit is null", () => {
  assert.equal(hitAt({ x: 0, y: 0 }, []), null);
});

const first = (tooltip) => tooltip.content.textContent.split("\n")[0];
const move = (handlers, x, y) => handlers.mousemove({ layerPoint: { x, y }, latlng: [-y, x] });

test("the listeners are registered once for the life of the layer, however often bands change", () => {
  const { counts, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands(twoStops);
  layer.setBands(twoStops);
  layer.setMaxWidth(20);
  assert.equal(counts.mousemove, 1);
  assert.equal(counts.mouseout, 1);
  assert.equal(counts.zoomend, 1);
});

test("a mouse move over the band shows one tooltip with the text of the stop, off it removes it", () => {
  const { handlers, tooltips, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  const far = [{ stops: [stop("A", 0, 100), stop("B", 100, 100)], color: "red" }];
  layer.setBands(far);
  assert.equal(tooltips.length, 1);
  const [tooltip] = tooltips;
  assert.equal(tooltip.options.sticky, false);
  assert.equal(tooltip.options.direction, "top");
  move(handlers, 3, 0);
  assert.equal(tooltip.open, true);
  assert.equal(tooltip.content.className, "manpower-tooltip");
  assert.equal(tooltip.content.textContent, stopText(far[0].stops[0]));
  assert.deepEqual(tooltip.latlng.map((n) => n + 0), [0, 3]);
  move(handlers, 60, 0);
  assert.equal(tooltip.content.textContent, stopText(far[0].stops[1]));
  assert.deepEqual(tooltip.latlng.map((n) => n + 0), [0, 60]);
  assert.equal(tooltips.length, 1);
  move(handlers, 5, 200);
  assert.equal(tooltip.open, false);
});

test("a wedge wins over the polygon beneath it", () => {
  const { handlers, tooltips, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100, 50), stop("B", 100, 100)], color: "red" }]);
  move(handlers, 0, -23);
  assert.equal(first(tooltips[0]), "A");
  move(handlers, 70, 0);
  assert.equal(first(tooltips[0]), "B");
});

test("a dotted step shows the tooltip within 8 px and not beyond", () => {
  const { handlers, tooltips, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100), stop("B", 100, null)], color: "red" }]);
  move(handlers, 80, 7);
  assert.equal(tooltips[0].open, true);
  assert.equal(tooltips[0].content.textContent, "B\nGeen aantal soldaten");
  move(handlers, 80, 9);
  assert.equal(tooltips[0].open, false);
});

test("the tooltip goes when the mouse leaves the map and when the bands go", () => {
  const { handlers, tooltips, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands(twoStops);
  move(handlers, 3, 0);
  handlers.mouseout();
  assert.equal(tooltips[0].open, false);
  move(handlers, 3, 0);
  assert.equal(tooltips[0].open, true);
  layer.setBands([]);
  assert.equal(tooltips[0].open, false);
  move(handlers, 3, 0);
  assert.equal(tooltips[0].open, false);
});

test("the shapes follow a zoom: after it the hit test uses the new layer points", () => {
  const { handlers, tooltips, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100), stop("B", 100, 100)], color: "red" }]);
  map.scale = 2;
  handlers.zoomend();
  move(handlers, 150, 0);
  assert.equal(first(tooltips[0]), "B");
  move(handlers, 40, 0);
  assert.equal(first(tooltips[0]), "A");
});

test("a viewreset (the pixel origin moves at the same zoom) rebuilds the shapes too", () => {
  const { added, handlers, counts, tooltips, map } = fakeLeaflet();
  const layer = createManpowerLayer(map);
  layer.setBands([{ stops: [stop("A", 0, 100), stop("B", 100, 100)], color: "red" }]);
  const before = of(added, "polygon")[0];
  map.scale = 2;
  handlers.viewreset();
  assert.equal(counts.viewreset, 1);
  assert.notEqual(of(added, "polygon")[0], before);
  move(handlers, 150, 0);
  assert.equal(first(tooltips[0]), "B");
});

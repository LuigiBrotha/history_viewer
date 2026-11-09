// The Manschappenband: along a Spoor a band whose width is the Manschappen of each Veldslag,
// flowing from one to the next, with a dark wedge on its edge for the losses. Widths are in
// pixels, so the same at every zoom; the band is worked out in layer points and drawn again
// whenever the map zooms.
import {
  bandSteps, clampBandWidth, DEFAULT_MAX_WIDTH, highestManpower, MAX_BAND_WIDTH, MIN_BAND_WIDTH, stopText, widthOf,
} from "./manpower.js";

const SCALE_MEN = 50000;
const PANE = "manpower";
const LOSS_PANE = "manpower-losses";
const LOSS_COLOR = "#2a2521";
const WEDGE_BASE = 12;
const DASH = "2 8";
const DOT_WEIGHT = 8;
const DOT_HIT = 8;
// A stop that stands alone, without a solid step on either side, is a rectangle this long.
const BOX_LENGTH = 12;
// How far a mitred corner may stick out, as a multiple of half the width (a turn of 120 degrees).
const MITER_LIMIT = 2;

// The four corners of the part of the band between a and b (points {x, y}), going from the
// left side of a to that of b and back along the right side. Null when a and b coincide. A join
// (see joinAt) replaces the flat end at a or b by the sharp corner it shares with the next part.
export function bandPolygon(a, b, widthA, widthB, joinA = null, joinB = null) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length === 0) return null;
  const nx = -dy / length;
  const ny = dx / length;
  const side = (p, w, sign) => ({ x: p.x + sign * nx * (w / 2), y: p.y + sign * ny * (w / 2) });
  return [
    joinA?.plus ?? side(a, widthA, 1),
    joinB?.plus ?? side(b, widthB, 1),
    joinB?.minus ?? side(b, widthB, -1),
    joinA?.minus ?? side(a, widthA, -1),
  ];
}

const normalOf = (tangent) => ({ x: -tangent.y, y: tangent.x });

// The two points where the sides of the band meet at a corner, for unit vectors along the band
// before and after it: { plus, minus }, on the same sides as bandPolygon. Null when the turn is
// so sharp that a mitre would become a long spike.
export function joinAt(point, before, after, width) {
  const n1 = normalOf(before);
  const n2 = normalOf(after);
  const sumX = n1.x + n2.x;
  const sumY = n1.y + n2.y;
  const length = Math.hypot(sumX, sumY);
  if (length < 1e-9) return null;
  const mx = sumX / length;
  const my = sumY / length;
  const stretch = 1 / (mx * n1.x + my * n1.y);
  if (stretch > MITER_LIMIT) return null;
  const off = (width / 2) * stretch;
  return {
    plus: { x: point.x + mx * off, y: point.y + my * off },
    minus: { x: point.x - mx * off, y: point.y - my * off },
  };
}

// A triangle on the left edge of the band as seen on screen (y points down) travelling along
// the unit vector tangent, 12 px along the band, pointing inward lossPx deep: never deeper than the band, at least 1 px.
export function lossWedge(point, tangent, width, lossPx) {
  const nx = tangent.y;
  const ny = -tangent.x;
  const depth = Math.max(1, Math.min(lossPx, width));
  const edge = { x: point.x + nx * (width / 2), y: point.y + ny * (width / 2) };
  const half = WEDGE_BASE / 2;
  return [
    { x: edge.x - tangent.x * half, y: edge.y - tangent.y * half },
    { x: edge.x + tangent.x * half, y: edge.y + tangent.y * half },
    { x: edge.x - nx * depth, y: edge.y - ny * depth },
  ];
}

// The length in px of the scale bar for 50.000 Manschappen, when the highest figure is maxPx wide.
export function scaleBar(highest, maxPx) {
  return { men: SCALE_MEN, px: highest > 0 ? widthOf(SCALE_MEN, highest, maxPx) : 0 };
}

const distance = (p, q) => Math.hypot(p.x - q.x, p.y - q.y);

function insidePolygon(point, corners) {
  let inside = false;
  for (let i = 0, j = corners.length - 1; i < corners.length; j = i++) {
    const a = corners[i];
    const b = corners[j];
    if ((a.y > point.y) !== (b.y > point.y) && point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

function distanceToSegment(point, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return distance(point, a);
  const t = Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / lengthSquared));
  return distance(point, { x: a.x + t * dx, y: a.y + t * dy });
}

const nearer = (point, { from, to }) => (distance(point, from.point) <= distance(point, to.point) ? from.stop : to.stop);

// The stop under point ({x, y} in layer points), or null. shapes are in priority order:
// { kind: "wedge", points, stop }, { kind: "box", points, stop },
// { kind: "polygon", points, from: { point, stop }, to: { point, stop } } and
// { kind: "step", from, to } for a dotted step, hit within 8 px.
export function hitAt(point, shapes) {
  for (const shape of shapes) {
    if ((shape.kind === "wedge" || shape.kind === "box") && insidePolygon(point, shape.points)) return shape.stop;
    if (shape.kind === "polygon" && insidePolygon(point, shape.points)) return nearer(point, shape);
    if (shape.kind === "step" && distanceToSegment(point, shape.from.point, shape.to.point) <= DOT_HIT) return nearer(point, shape);
  }
  return null;
}

// The unit vector along the band at stop i: the step leaving it, else the one arriving, skipping
// stops on the very same spot. Null when there is no direction at all.
function tangentAt(points, i) {
  const unit = (from, to) => {
    const length = Math.hypot(to.x - from.x, to.y - from.y);
    return length === 0 ? null : { x: (to.x - from.x) / length, y: (to.y - from.y) / length };
  };
  for (let j = i + 1; j < points.length; j++) {
    const t = unit(points[i], points[j]);
    if (t) return t;
  }
  for (let j = i - 1; j >= 0; j--) {
    const t = unit(points[j], points[i]);
    if (t) return t;
  }
  return null;
}

export function createManpowerLayer(map, { onWidthChange } = {}) {
  for (const [name, z] of [[PANE, 385], [LOSS_PANE, 386]]) {
    map.createPane(name);
    map.getPane(name).style.zIndex = z;
  }
  map.getPane(PANE).style.opacity = 0.55;
  const group = L.layerGroup().addTo(map);
  let drawn = [];
  let bands = [];
  let shapes = [];
  const tooltip = L.tooltip({ sticky: false, direction: "top", className: "manpower-tooltip-box" });
  let tooltipOpen = false;
  let maxWidth = DEFAULT_MAX_WIDTH;

  const highest = () => bands.reduce((max, band) => Math.max(max, highestManpower(band.stops)), 0);
  const add = (layer) => {
    group.addLayer(layer);
    drawn.push(layer);
  };
  const toLatLngs = (points) => points.map((p) => map.layerPointToLatLng(p));
  const still = { interactive: false };

  // Draws one band and returns its shapes for the hit test: wedges, boxes, polygons, dotted steps.
  function drawBand({ stops, color }, top) {
    const points = stops.map((s) => map.latLngToLayerPoint([s.battle.lat, s.battle.lng]));
    const widths = stops.map((s) => (s.manpower ? widthOf(s.manpower.total, top, maxWidth) : 0));
    const ends = (i) => ({ point: points[i], stop: stops[i] });
    const found = { wedges: [], boxes: [], polygons: [], steps: [] };
    const fill = (corners) => add(L.polygon(toLatLngs(corners), { pane: PANE, stroke: false, fillColor: color, fillOpacity: 1, ...still }));
    const box = (corners, stop) => {
      fill(corners);
      found.boxes.push({ kind: "box", points: corners, stop });
    };
    const steps = bandSteps(stops);
    // Per step the unit vector along it: null for a dotted step or two stops on the same spot.
    const along = steps.map((step, i) => {
      const length = distance(points[i], points[i + 1]);
      if (!step.solid || length === 0) return null;
      return { x: (points[i + 1].x - points[i].x) / length, y: (points[i + 1].y - points[i].y) / length };
    });
    // Where two solid steps meet: a shared sharp corner, or for a sharp turn two straight triangles.
    const joins = stops.map((_, i) => {
      if (!along[i - 1] || !along[i]) return null;
      const join = joinAt(points[i], along[i - 1], along[i], widths[i]);
      if (join) return join;
      const half = widths[i] / 2;
      const edge = (t, sign) => ({ x: points[i].x + sign * normalOf(t).x * half, y: points[i].y + sign * normalOf(t).y * half });
      for (const sign of [1, -1]) box([points[i], edge(along[i - 1], sign), edge(along[i], sign)], stops[i]);
      return null;
    });
    steps.forEach((step, i) => {
      if (!step.solid) {
        add(L.polyline([[step.from.battle.lat, step.from.battle.lng], [step.to.battle.lat, step.to.battle.lng]],
          { pane: PANE, color, weight: DOT_WEIGHT, dashArray: DASH, lineCap: "butt", ...still }));
        found.steps.push({ kind: "step", from: ends(i), to: ends(i + 1) });
        return;
      }
      const corners = bandPolygon(points[i], points[i + 1], widths[i], widths[i + 1], joins[i], joins[i + 1]);
      if (!corners) return;
      fill(corners);
      found.polygons.push({ kind: "polygon", points: corners, from: ends(i), to: ends(i + 1) });
    });
    // A figure with no solid step beside it: a short rectangle across the line.
    stops.forEach((s, i) => {
      if (!s.manpower || along[i - 1] || along[i]) return;
      const t = tangentAt(points, i) ?? { x: 1, y: 0 };
      const end = (sign) => ({ x: points[i].x + sign * t.x * (BOX_LENGTH / 2), y: points[i].y + sign * t.y * (BOX_LENGTH / 2) });
      box(bandPolygon(end(-1), end(1), widths[i], widths[i]), s);
    });
    stops.forEach((s, i) => {
      if (!s.manpower || s.loss == null) return;
      const tangent = tangentAt(points, i);
      if (!tangent) return;
      const wedge = lossWedge(points[i], tangent, widths[i], widthOf(s.loss, top, maxWidth));
      add(L.polygon(toLatLngs(wedge), { pane: LOSS_PANE, stroke: false, fillColor: LOSS_COLOR, fillOpacity: 1, ...still }));
      found.wedges.push({ kind: "wedge", points: wedge, stop: s });
    });
    return found;
  }

  // The slider and the legend, in the corner for as long as there is a band.
  let control = null;
  let shown = false;
  let slider = null;
  let bar = null;
  const buildControl = () => {
    const box = L.DomUtil.create("div", "manpower-control");
    L.DomEvent.disableClickPropagation(box);
    L.DomEvent.disableScrollPropagation(box);
    const label = document.createElement("label");
    label.className = "manpower-control-label";
    label.textContent = "Dikte band";
    slider = document.createElement("input");
    slider.type = "range";
    slider.min = MIN_BAND_WIDTH;
    slider.max = MAX_BAND_WIDTH;
    slider.step = 1;
    slider.value = maxWidth;
    slider.addEventListener("input", () => {
      const px = clampBandWidth(slider.value);
      if (px === undefined) return;
      maxWidth = px;
      redraw();
      onWidthChange?.(px);
    });
    label.append(slider);
    const scale = document.createElement("div");
    scale.className = "manpower-scale";
    bar = document.createElement("span");
    bar.className = "manpower-scale-bar";
    const barText = document.createElement("span");
    barText.textContent = "50.000 Manschappen";
    scale.append(bar, barText);
    const note = document.createElement("div");
    note.className = "manpower-note";
    note.textContent = "Cijfer per kant, niet per Bevelhebber";
    box.append(label, scale, note);
    box.bar = bar;
    return box;
  };
  function syncControl() {
    if (!bands.length) {
      if (shown) control.remove();
      shown = false;
      return;
    }
    if (!control) {
      control = L.control({ position: "bottomleft" });
      control.onAdd = buildControl;
    }
    if (!shown) control.addTo(map);
    shown = true;
    slider.value = maxWidth;
    const { px } = scaleBar(highest(), maxWidth);
    bar.style.display = px > 0 ? "" : "none";
    bar.style.width = `${px}px`;
  }

  function redraw() {
    drawn.forEach((layer) => group.removeLayer(layer));
    drawn = [];
    const top = highest();
    const found = bands.map((band) => drawBand(band, top));
    shapes = ["wedges", "boxes", "polygons", "steps"].flatMap((kind) => found.flatMap((f) => f[kind]));
    if (!shapes.length) hideTooltip();
    syncControl();
  }
  map.on("zoomend", redraw);
  map.on("viewreset", redraw);

  // One hit test for the whole map: the band lets every mouse event through.
  function hideTooltip() {
    if (tooltipOpen) tooltip.remove();
    tooltipOpen = false;
  }
  map.on("mousemove", (e) => {
    if (!shapes.length) return;
    const hit = hitAt(e.layerPoint, shapes);
    if (!hit) {
      hideTooltip();
      return;
    }
    const content = document.createElement("div");
    content.className = "manpower-tooltip";
    content.textContent = stopText(hit);
    tooltip.setContent(content).setLatLng(e.latlng);
    if (!tooltipOpen) tooltip.addTo(map);
    tooltipOpen = true;
  });
  map.on("mouseout", hideTooltip);

  return {
    // bands: [{ stops (see bandStops), color }]
    setBands(next) {
      bands = next;
      redraw();
    },
    // From the URL or the page: not reported back.
    setMaxWidth(px) {
      maxWidth = px;
      redraw();
    },
    maxWidth: () => maxWidth,
    highest,
  };
}

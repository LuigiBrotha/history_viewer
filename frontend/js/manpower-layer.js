// The Manschappenband: along a Spoor a band whose width is the Manschappen of each Veldslag,
// flowing from one to the next, with a dark wedge on its edge for the losses. Widths are in
// pixels, so the same at every zoom; the band is worked out in layer points and drawn again
// whenever the map zooms.
import { bandSteps, highestManpower, stopText, widthOf } from "./manpower.js";

export const DEFAULT_MAX_WIDTH = 48;
const PANE = "manpower";
const LOSS_PANE = "manpower-losses";
const LOSS_COLOR = "#2a2521";
const WEDGE_BASE = 12;
const DASH = "4 6";

// The four corners of the part of the band between a and b (points {x, y}), going from the
// left side of a to that of b and back along the right side. Null when a and b coincide.
export function bandPolygon(a, b, widthA, widthB) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length === 0) return null;
  const nx = -dy / length;
  const ny = dx / length;
  const side = (p, w, sign) => ({ x: p.x + sign * nx * (w / 2), y: p.y + sign * ny * (w / 2) });
  return [side(a, widthA, 1), side(b, widthB, 1), side(b, widthB, -1), side(a, widthA, -1)];
}

// A triangle on the left edge of the band (left of the unit vector tangent), 12 px along the
// band, pointing inward lossPx deep: never deeper than the band, at least 1 px.
export function lossWedge(point, tangent, width, lossPx) {
  const nx = -tangent.y;
  const ny = tangent.x;
  const depth = Math.max(1, Math.min(lossPx, width));
  const edge = { x: point.x + nx * (width / 2), y: point.y + ny * (width / 2) };
  const half = WEDGE_BASE / 2;
  return [
    { x: edge.x - tangent.x * half, y: edge.y - tangent.y * half },
    { x: edge.x + tangent.x * half, y: edge.y + tangent.y * half },
    { x: edge.x - nx * depth, y: edge.y - ny * depth },
  ];
}

function tooltipElement(text) {
  const element = document.createElement("div");
  element.className = "manpower-tooltip";
  element.textContent = text;
  return element;
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

export function createManpowerLayer(map) {
  for (const [name, z] of [[PANE, 395], [LOSS_PANE, 396]]) {
    map.createPane(name);
    map.getPane(name).style.zIndex = z;
  }
  map.getPane(PANE).style.opacity = 0.55;
  const group = L.layerGroup().addTo(map);
  let drawn = [];
  let bands = [];
  let maxWidth = DEFAULT_MAX_WIDTH;

  const highest = () => bands.reduce((max, band) => Math.max(max, highestManpower(band.stops)), 0);
  const add = (layer, text) => {
    layer.bindTooltip(tooltipElement(text), { sticky: true });
    group.addLayer(layer);
    drawn.push(layer);
  };
  const toLatLngs = (points) => points.map((p) => map.layerPointToLatLng(p));

  function drawBand({ stops, color }, top) {
    const points = stops.map((s) => map.latLngToLayerPoint([s.battle.lat, s.battle.lng]));
    const widths = stops.map((s) => (s.manpower ? widthOf(s.manpower.total, top, maxWidth) : 0));
    bandSteps(stops).forEach((step, i) => {
      const text = `${stopText(step.from)}\n\n${stopText(step.to)}`;
      if (!step.solid) {
        add(L.polyline([[step.from.battle.lat, step.from.battle.lng], [step.to.battle.lat, step.to.battle.lng]],
          { pane: PANE, color, weight: 2, dashArray: DASH }), text);
        return;
      }
      const corners = bandPolygon(points[i], points[i + 1], widths[i], widths[i + 1]);
      if (corners) add(L.polygon(toLatLngs(corners), { pane: PANE, stroke: false, fillColor: color, fillOpacity: 1 }), text);
    });
    stops.forEach((s, i) => {
      if (!s.manpower) return;
      add(L.circleMarker([s.battle.lat, s.battle.lng],
        { pane: PANE, radius: widths[i] / 2, stroke: false, fillColor: color, fillOpacity: 1 }), stopText(s));
    });
    stops.forEach((s, i) => {
      if (!s.manpower || s.loss == null) return;
      const tangent = tangentAt(points, i);
      if (!tangent) return;
      const wedge = lossWedge(points[i], tangent, widths[i], widthOf(s.loss, top, maxWidth));
      add(L.polygon(toLatLngs(wedge), { pane: LOSS_PANE, stroke: false, fillColor: LOSS_COLOR, fillOpacity: 1 }), stopText(s));
    });
  }

  function redraw() {
    drawn.forEach((layer) => group.removeLayer(layer));
    drawn = [];
    const top = highest();
    bands.forEach((band) => drawBand(band, top));
  }
  map.on("zoomend", redraw);

  return {
    // bands: [{ stops (see bandStops), color }]
    setBands(next) {
      bands = next;
      redraw();
    },
    setMaxWidth(px) {
      maxWidth = px;
      redraw();
    },
    maxWidth: () => maxWidth,
    highest,
  };
}

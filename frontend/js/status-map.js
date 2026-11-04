import { turboColor } from "./color-ramp.js";
import { datedPoints, legStyle } from "./time-model.js";

const LAST_COLOR = "#000000";
const UNDATED_COLOR = "#888888";
const LINE_WEIGHT = 0.75;
const LINE_OPACITY = 0.9;
const MARKER_RADIUS = 2;
// Lines this thin are hard to hit, by finger above all.
const HIT_TOLERANCE_PX = 8;

export function patrolStart(patrol) {
  return patrol.departure_date ?? datedPoints(patrol)[0]?.date ?? null;
}

export function patrolEnd(patrol) {
  return patrol.arrival_date ?? datedPoints(patrol).at(-1)?.date ?? patrolStart(patrol);
}

export function historyRange(patrols) {
  const starts = patrols.map(patrolStart).filter((date) => date !== null).sort();
  return starts.length === 0 ? null : { min: starts[0], max: starts[starts.length - 1] };
}

export function rampValue(date, history) {
  const min = Date.parse(history.min);
  const span = Date.parse(history.max) - min;
  return span === 0 ? 0 : (Date.parse(date) - min) / span;
}

export function routeColor(patrol, lastExternalId, history) {
  if (patrol.external_id === lastExternalId) {
    return LAST_COLOR;
  }
  const start = patrolStart(patrol);
  return start === null || history === null ? UNDATED_COLOR : turboColor(rampValue(start, history));
}

// A patrol belongs to a period when the two overlap. Without dates it cannot be placed in one.
export function inPeriod(patrol, from, to) {
  if (from === null && to === null) {
    return true;
  }
  const start = patrolStart(patrol);
  if (start === null) {
    return false;
  }
  if (from !== null && to !== null && from > to) {
    return false;
  }
  return (from === null || patrolEnd(patrol) >= from) && (to === null || start <= to);
}

export function routeTooltip(patrol) {
  const name = `${patrol.boat_number} — ${patrol.external_id}`;
  const start = patrolStart(patrol);
  return start === null ? name : `${name} — ${start} t/m ${patrolEnd(patrol)}`;
}

// On this page every drawable leg takes the page's colour; suspect is not orange.
export function statusLegStyle(status, color) {
  const style = legStyle(status === "suspect" ? "ok" : status);
  return style === null ? null : { ...style, color };
}

function pointLatLngs(patrol) {
  return patrol.points.map((point) => [point.lat, point.lng]);
}

function drawablePaths(patrol) {
  return (patrol.legs ?? [])
    .filter((leg) => statusLegStyle(leg.status, UNDATED_COLOR) !== null && leg.path)
    .map((leg) => leg.path);
}

export function newStatusState(map, layer) {
  return {
    map,
    layer,
    patrols: new Map(),
    polylines: new Map(),
    markers: new Set(),
    extents: new Map(),
    history: null,
    from: null,
    to: null,
    fitted: false,
    lastExternalId: null,
  };
}

export function createStatusMap(containerId) {
  const map = L.map(containerId, { renderer: L.canvas({ tolerance: HIT_TOLERANCE_PX }) }).setView([54.5, 8.0], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  return newStatusState(map, L.featureGroup().addTo(map));
}

function applyColor(state, externalId, polyline) {
  const color = routeColor(state.patrols.get(externalId), state.lastExternalId, state.history);
  const style = { color, weight: LINE_WEIGHT };
  if (!state.markers.has(externalId)) {
    style.dashArray = statusLegStyle("ok", color).dashArray;
  }
  polyline.setStyle(style);
}

function bringLastToFront(state) {
  const last = state.polylines.get(state.lastExternalId);
  if (last && state.layer.hasLayer(last)) {
    last.bringToFront();
  }
}

function drawPatrol(state, patrol) {
  const id = patrol.external_id;
  const existing = state.polylines.get(id);
  if (existing) {
    state.layer.removeLayer(existing);
    state.polylines.delete(id);
  }
  state.markers.delete(id);
  state.extents.delete(id);
  if (patrol.points.length === 0) {
    return;
  }
  state.extents.set(id, pointLatLngs(patrol));
  let polyline;
  if (patrol.points.length === 1) {
    polyline = L.circleMarker(pointLatLngs(patrol)[0], { radius: MARKER_RADIUS, fillOpacity: LINE_OPACITY });
    state.markers.add(id);
  } else {
    const paths = drawablePaths(patrol);
    if (paths.length === 0) {
      return;
    }
    polyline = L.polyline(paths, { weight: LINE_WEIGHT, opacity: LINE_OPACITY });
  }
  polyline.bindTooltip(routeTooltip(patrol), { sticky: true });
  state.polylines.set(id, polyline);
  applyColor(state, id, polyline);
  if (inPeriod(patrol, state.from, state.to)) {
    state.layer.addLayer(polyline);
  }
}

// Adds or replaces the polylines of the given patrols; the rest are only recoloured
// when these patrols moved the oldest or newest date.
export function updateRoutes(state, changed) {
  for (const patrol of changed) {
    state.patrols.set(patrol.external_id, patrol);
  }
  const previous = state.history;
  state.history = historyRange([...state.patrols.values()]);

  for (const patrol of changed) {
    drawPatrol(state, patrol);
  }
  if (previous?.min !== state.history?.min || previous?.max !== state.history?.max) {
    for (const [id, polyline] of state.polylines) {
      applyColor(state, id, polyline);
    }
  }
  bringLastToFront(state);

  if (!state.fitted && state.extents.size > 0) {
    state.fitted = true;
    state.map.fitBounds([...state.extents.values()].flat(), { padding: [40, 40] });
  }
}

// Recolours so only the last crawled patrol is black. A patrol whose route has not
// arrived yet is coloured by updateRoutes once it does.
export function setLastPatrol(state, externalId) {
  const previous = state.lastExternalId;
  state.lastExternalId = externalId;
  for (const id of new Set([previous, externalId])) {
    const polyline = state.polylines.get(id);
    if (polyline) {
      applyColor(state, id, polyline);
    }
  }
  bringLastToFront(state);
}

export function setPeriod(state, from, to) {
  state.from = from;
  state.to = to;
  for (const [id, polyline] of state.polylines) {
    const shown = inPeriod(state.patrols.get(id), from, to);
    if (shown && !state.layer.hasLayer(polyline)) {
      state.layer.addLayer(polyline);
    } else if (!shown && state.layer.hasLayer(polyline)) {
      state.layer.removeLayer(polyline);
    }
  }
  bringLastToFront(state);
}

export function visibleCount(state) {
  const lines = [...state.polylines.values()];
  return { visible: lines.filter((line) => state.layer.hasLayer(line)).length, total: lines.length };
}

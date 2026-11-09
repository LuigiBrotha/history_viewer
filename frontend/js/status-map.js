import { addBaseMaps } from "./base-maps.js";
import { turboColor } from "./color-ramp.js";
import { datedPoints, legStyle } from "./time-model.js";

const LAST_COLOR = "#000000";
const UNDATED_COLOR = "#888888";
const LINE_WEIGHT = 0.75;
const LINE_OPACITY = 0.9;
const HIGHLIGHT_WEIGHT = 3;
const OTHER_BOAT_COLOR = "#9a9a9a";
const SELECTED_WEIGHT = 1.5;
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

// The dates the ramp stretches over: the selected period, or all of history.
export function colorRange(history, from, to) {
  if (history === null) {
    return null;
  }
  return { min: from ?? history.min, max: to ?? history.max };
}

// A patrol that departed before colorRange's start clamps to the ramp's lowest colour.
export function routeColor(patrol, lastExternalId, range) {
  if (patrol.external_id === lastExternalId) {
    return LAST_COLOR;
  }
  const start = patrolStart(patrol);
  return start === null || range === null ? UNDATED_COLOR : turboColor(rampValue(start, range));
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
    knownHistory: null,
    fitView: null,
    from: null,
    to: null,
    fitted: false,
    lastExternalId: null,
    highlightedExternalId: null,
    selectedSlug: null,
  };
}

export function createStatusMap(containerId) {
  const map = L.map(containerId, { renderer: L.canvas({ tolerance: HIT_TOLERANCE_PX }) }).setView([54.5, 8.0], 5);

  addBaseMaps(map);

  return newStatusState(map, L.featureGroup().addTo(map));
}

function applyColor(state, externalId, polyline) {
  const range = colorRange(state.history, state.from, state.to);
  const patrol = state.patrols.get(externalId);
  const isSelected = state.selectedSlug !== null && patrol.boat_slug === state.selectedSlug;
  const greyed = state.selectedSlug !== null && !isSelected;
  const color = greyed ? OTHER_BOAT_COLOR : routeColor(patrol, state.lastExternalId, range);
  let weight = isSelected ? SELECTED_WEIGHT : LINE_WEIGHT;
  if (externalId === state.highlightedExternalId) {
    weight = HIGHLIGHT_WEIGHT;
  }
  const style = { color, weight };
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
  polyline.on("click", () => state.onRouteClick?.(state.patrols.get(id)));
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
  state.history = state.knownHistory ?? historyRange([...state.patrols.values()]);

  for (const patrol of changed) {
    drawPatrol(state, patrol);
  }
  if (previous?.min !== state.history?.min || previous?.max !== state.history?.max) {
    for (const [id, polyline] of state.polylines) {
      if (inPeriod(state.patrols.get(id), state.from, state.to)) {
        applyColor(state, id, polyline);
      }
    }
  }
  if (state.selectedSlug === null) {
    bringLastToFront(state);
  }

  if (!state.fitted && state.extents.size > 0) {
    state.fitted = true;
    state.map.fitBounds([...state.extents.values()].flat(), { padding: [40, 40], animate: false });
    state.fitView = viewOf(state.map);
  }
}

export function viewOf(map) {
  const { lat, lng } = map.getCenter();
  return { lat, lng, zoom: map.getZoom() };
}

export function sameView(map, view) {
  const now = viewOf(map);
  return now.zoom === view.zoom && Math.abs(now.lat - view.lat) < 1e-6 && Math.abs(now.lng - view.lng) < 1e-6;
}

// The span of all patrols, from before their routes have arrived: colours stay as they are while
// the rest comes in.
export function setHistory(state, history) {
  if (state.knownHistory?.min === history.min && state.knownHistory?.max === history.max) return;
  state.knownHistory = history;
  state.history = history;
  recolorAll(state);
}

// The map was fitted to what had arrived first; now all of it is in, unless the user has moved it.
export function fitAllRoutes(state) {
  const view = state.fitView;
  state.fitView = null;
  if (view !== null && sameView(state.map, view)) {
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

function recolorAll(state) {
  for (const [id, polyline] of state.polylines) {
    applyColor(state, id, polyline);
  }
}

// With a boat selected, only its own routes keep their colours; null shows all again.
export function selectBoat(state, slug) {
  state.selectedSlug = slug;
  state.highlightedExternalId = null;
  recolorAll(state);
  raiseChosen(state);
}

// The selected boat's routes on top; without a selection, the last crawled patrol.
function raiseChosen(state) {
  if (state.selectedSlug === null) {
    bringLastToFront(state);
    return;
  }
  for (const [id, polyline] of state.polylines) {
    if (state.patrols.get(id).boat_slug === state.selectedSlug && state.layer.hasLayer(polyline)) {
      polyline.bringToFront();
    }
  }
}

// Coming back, the lines are drawn in the order they were added, so the chosen ones are raised again.
export function setBoatsVisible(state, visible) {
  if (visible === state.map.hasLayer(state.layer)) {
    return;
  }
  if (!visible) {
    state.map.removeLayer(state.layer);
    return;
  }
  state.map.addLayer(state.layer);
  raiseChosen(state);
}

// All routes of a boat in view.
export function fitBoat(state, slug) {
  const points = [];
  for (const [id, patrol] of state.patrols) {
    if (patrol.boat_slug === slug && state.extents.has(id)) points.push(...state.extents.get(id));
  }
  if (points.length > 0) state.map.fitBounds(points, { padding: [40, 40] });
}

// Shows one patrol's route clearly among all the others.
export function highlightPatrol(state, externalId) {
  const polyline = state.polylines.get(externalId);
  if (polyline === undefined) {
    return;
  }
  const previousId = state.highlightedExternalId;
  state.highlightedExternalId = externalId;
  const previous = state.polylines.get(previousId);
  if (previous) {
    applyColor(state, previousId, previous);
  }
  applyColor(state, externalId, polyline);
  if (!state.layer.hasLayer(polyline)) {
    state.layer.addLayer(polyline);
  }
  polyline.bringToFront();
  state.map.fitBounds(state.extents.get(externalId), { padding: [40, 40] });
}

export function setPeriod(state, from, to) {
  state.from = from;
  state.to = to;
  for (const [id, polyline] of state.polylines) {
    const shown = inPeriod(state.patrols.get(id), from, to);
    if (shown) {
      applyColor(state, id, polyline);
    }
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

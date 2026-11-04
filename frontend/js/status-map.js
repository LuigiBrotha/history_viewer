import { legStyle } from "./time-model.js";

const LAST_COLOR = "#cc3300";
const OTHER_COLOR = "#0077cc";

export function routeColor(patrol, lastExternalId) {
  return patrol.external_id === lastExternalId ? LAST_COLOR : OTHER_COLOR;
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
    .filter((leg) => statusLegStyle(leg.status, OTHER_COLOR) !== null && leg.path)
    .map((leg) => leg.path);
}

export function createStatusMap(containerId) {
  const map = L.map(containerId, { preferCanvas: true }).setView([54.5, 8.0], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const layer = L.featureGroup().addTo(map);
  return { map, layer, polylines: new Map(), markers: new Set(), extents: new Map(), fitted: false, lastExternalId: null };
}

function applyColor(state, externalId, polyline) {
  const color = routeColor({ external_id: externalId }, state.lastExternalId);
  const style = { color, weight: color === LAST_COLOR ? 3 : 2 };
  if (!state.markers.has(externalId)) {
    style.dashArray = statusLegStyle("ok", color).dashArray;
  }
  polyline.setStyle(style);
  if (color === LAST_COLOR) {
    polyline.bringToFront();
  }
}

// Adds or replaces the polylines of the given patrols; the rest are left alone.
export function updateRoutes(state, changed) {
  for (const patrol of changed) {
    const existing = state.polylines.get(patrol.external_id);
    if (existing) {
      state.layer.removeLayer(existing);
      state.polylines.delete(patrol.external_id);
    }
    state.markers.delete(patrol.external_id);
    state.extents.delete(patrol.external_id);
    if (patrol.points.length === 0) {
      continue;
    }
    state.extents.set(patrol.external_id, pointLatLngs(patrol));
    let polyline;
    if (patrol.points.length === 1) {
      polyline = L.circleMarker(pointLatLngs(patrol)[0], { radius: 4, fillOpacity: 0.8 });
      state.markers.add(patrol.external_id);
    } else {
      const paths = drawablePaths(patrol);
      if (paths.length === 0) {
        continue;
      }
      polyline = L.polyline(paths, { weight: 2, opacity: 0.8 });
    }
    polyline.bindTooltip(`${patrol.boat_number} — ${patrol.external_id}`, { sticky: true });
    polyline.addTo(state.layer);
    state.polylines.set(patrol.external_id, polyline);
    applyColor(state, patrol.external_id, polyline);
  }

  // Newly drawn blue routes must not cover the last crawled one.
  const last = state.polylines.get(state.lastExternalId);
  if (last) {
    last.bringToFront();
  }

  if (!state.fitted && state.extents.size > 0) {
    state.fitted = true;
    state.map.fitBounds([...state.extents.values()].flat(), { padding: [40, 40] });
  }
}

// Recolours so only the last crawled patrol is red. A patrol whose route has not
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
}

const LAST_COLOR = "#cc3300";
const OTHER_COLOR = "#0077cc";

export function routeColor(patrol, lastExternalId) {
  return patrol.external_id === lastExternalId ? LAST_COLOR : OTHER_COLOR;
}

export function routeLatLngs(patrol) {
  return patrol.points.map((point) => [point.lat, point.lng]);
}

export function createStatusMap(containerId) {
  const map = L.map(containerId, { preferCanvas: true }).setView([54.5, 8.0], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const layer = L.featureGroup().addTo(map);
  return { map, layer, polylines: new Map(), fitted: false, lastExternalId: null };
}

function applyColor(state, externalId, polyline) {
  const color = routeColor({ external_id: externalId }, state.lastExternalId);
  polyline.setStyle({ color, weight: color === LAST_COLOR ? 3 : 2 });
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
    if (patrol.points.length < 2) {
      continue;
    }
    const polyline = L.polyline(routeLatLngs(patrol), { weight: 2, opacity: 0.8 });
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

  if (!state.fitted && state.polylines.size > 0) {
    state.fitted = true;
    state.map.fitBounds(state.layer.getBounds(), { padding: [40, 40] });
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

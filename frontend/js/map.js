import { addBaseMaps } from "./base-maps.js";
import { boatColor } from "./boat-color.js";
import { reopenPoint } from "./edit-state.js";
import { legMidpoint, legStyle, positionLabel, shouldFitRoute, tailLeg } from "./time-model.js";

const UNCERTAIN = new Set(["on_land", "no_route"]);
const ROUTE_UNCERTAIN = " — route onzeker";
const ROUTES_PANE = "routes";
// Below Leaflet's overlay pane (400), so that the boats lie on their routes.
const ROUTES_Z_INDEX = 390;
const BOATS_PANE = "boats";
// Above the routes, below the ships (450).
const BOATS_Z_INDEX = 410;

export function createMap(containerId) {
  const map = L.map(containerId).setView([54.5, 8.0], 5);

  addBaseMaps(map);

  map.createPane(ROUTES_PANE);
  map.getPane(ROUTES_PANE).style.zIndex = ROUTES_Z_INDEX;
  map.createPane(BOATS_PANE);
  map.getPane(BOATS_PANE).style.zIndex = BOATS_Z_INDEX;

  const activeBoatsLayer = L.layerGroup().addTo(map);
  const followedRouteLayer = L.layerGroup().addTo(map);

  return { map, activeBoatsLayer, followedRouteLayer, fittedExternalId: null };
}

const MOUSE_DOT_RADIUS = 3;
const FINGER_DOT_RADIUS = 7;
const COARSE_POINTER = () => globalThis.matchMedia?.("(pointer: coarse)").matches ?? false;

export function dotRadius(coarsePointer) {
  return coarsePointer ? FINGER_DOT_RADIUS : MOUSE_DOT_RADIUS;
}

// A hollow marker: the position is known, but its date is an approximation.
const APPROXIMATE_FILL = 0.2;

// A suspect leg keeps its warning colour; every other leg takes the boat's colour.
function boatLegStyle(style, status, color) {
  return status === "suspect" ? style : { ...style, color };
}

export function renderActiveBoats(mapState, activeBoats, onBoatClick) {
  mapState.activeBoatsLayer.clearLayers();

  for (const boat of activeBoats) {
    const color = boatColor(boat.boatSlug);
    const leg = tailLeg(boat.patrol, boat);
    const style = leg === null ? null : legStyle(leg.status);
    if (style !== null && leg.path) {
      L.polyline(leg.path, { ...boatLegStyle(style, leg.status, color), weight: 2, opacity: 0.6, interactive: false, pane: ROUTES_PANE }).addTo(
        mapState.activeBoatsLayer,
      );
    }

    const marker = L.circleMarker([boat.lat, boat.lng], {
      radius: 6,
      color,
      fillColor: color,
      fillOpacity: boat.dateApproximate ? APPROXIMATE_FILL : 0.85,
      pane: BOATS_PANE,
    });
    const uncertain = leg !== null && UNCERTAIN.has(leg.status);
    marker.bindTooltip(uncertain ? `${positionLabel(boat)}${ROUTE_UNCERTAIN}` : positionLabel(boat));
    marker.on("click", () => onBoatClick(boat.boatSlug));
    marker.addTo(mapState.activeBoatsLayer);
  }
}

export function pointPopup(point, { onExclude, busy }) {
  const box = document.createElement("div");
  const line = document.createElement("div");
  const date = point.date ?? "geen datum";
  line.textContent = point.date && point.date_approximate ? `${date} (datum benaderd)` : date;
  box.appendChild(line);
  if (onExclude !== null) {
    const button = document.createElement("button");
    button.textContent = busy ? "Bezig…" : "Punt uitsluiten";
    button.disabled = busy;
    button.addEventListener("click", () => onExclude(point, button));
    box.appendChild(button);
  }
  return box;
}

// fit is true for user actions (boat selected, date changed). A live update passes
// false: it redraws the route but leaves the user's zoom alone.
// onExclude is null when editing is not allowed: the popup then only shows the date.
// isBusy(point) says whether a request for the point is running.
// A popup that was open is opened again, without panning, if that point of that patrol is still drawn.
export function renderFollowedRoute(mapState, patrol, currentPosition, { fit, onExclude = null, isBusy = () => false }) {
  const reopen = reopenPoint(mapState.openPoint, patrol);
  mapState.openPoint = reopen;
  // Clearing the layer closes the popup; that is not the user closing it.
  mapState.redrawing = true;
  mapState.followedRouteLayer.clearLayers();
  mapState.redrawing = false;

  if (patrol === null) {
    return;
  }

  const layer = mapState.followedRouteLayer;

  function bindPointPopup(marker, point) {
    if (!marker.bindPopup) {
      return;
    }
    const isReopen = reopen !== null && point.sequence === reopen.sequence;
    // A reopened popup must not pan the map the user may be looking at elsewhere.
    marker.bindPopup(() => pointPopup(point, { onExclude, busy: isBusy(point) }), { autoPan: !isReopen });
    marker.on("popupopen", () => {
      mapState.openPoint = { externalId: patrol.external_id, sequence: point.sequence, lat: point.lat, lng: point.lng };
    });
    marker.on("popupclose", () => {
      if (!mapState.redrawing) {
        mapState.openPoint = null;
      }
    });
    if (isReopen) {
      marker.openPopup();
    }
  }

  const fitPoints = patrol.points.map((point) => [point.lat, point.lng]);
  const color = boatColor(patrol.boat_slug ?? "");

  for (const leg of patrol.legs ?? []) {
    const style = legStyle(leg.status);
    if (style !== null && leg.path) {
      const line = L.polyline(leg.path, { ...boatLegStyle(style, leg.status, color), weight: 3, pane: ROUTES_PANE }).addTo(layer);
      if (leg.status === "suspect") {
        line.bindTooltip(leg.reason);
      }
      fitPoints.push(...leg.path);
    }
    if (UNCERTAIN.has(leg.status)) {
      const midpoint = legMidpoint(leg, patrol);
      if (midpoint !== null) {
        const icon = L.divIcon({ className: "leg-uncertain", html: "?", iconSize: [18, 18] });
        L.marker(midpoint, { icon, pane: ROUTES_PANE }).bindTooltip(leg.reason).addTo(layer);
      }
    }
  }

  for (const point of patrol.points) {
    const dot = L.circleMarker([point.lat, point.lng], {
      radius: dotRadius(COARSE_POINTER()),
      color,
      fillColor: color,
      fillOpacity: 1,
      pane: ROUTES_PANE,
    }).addTo(layer);
    // The marker of the current position covers its dot, so that marker carries the popup.
    if (point.sequence !== currentPosition?.sequence) {
      bindPointPopup(dot, point);
    }
  }

  if (currentPosition !== null) {
    const marker = L.circleMarker([currentPosition.lat, currentPosition.lng], {
      radius: 8,
      color: "#000000",
      fillColor: color,
      fillOpacity: currentPosition.dateApproximate ? APPROXIMATE_FILL : 1,
      pane: BOATS_PANE,
    })
      .bindTooltip(
        positionLabel({
          boatNumber: patrol.boat_number,
          positionDate: currentPosition.date,
          dateApproximate: currentPosition.dateApproximate,
        }),
      )
      .addTo(layer);
    const point = patrol.points.find((candidate) => candidate.sequence === currentPosition.sequence)
      ?? { sequence: currentPosition.sequence, lat: currentPosition.lat, lng: currentPosition.lng, date: currentPosition.date, date_approximate: currentPosition.dateApproximate };
    bindPointPopup(marker, point);
  }

  if (shouldFitRoute(mapState.fittedExternalId, patrol)) {
    mapState.fittedExternalId = patrol.external_id;
    if (fit) {
      mapState.map.fitBounds(fitPoints, { padding: [40, 40] });
    }
  }
}

// Hides what the boats sailed; the boats themselves stay. A popup may hang on a hidden dot.
export function setRoutesVisible(mapState, visible) {
  setPaneVisible(mapState, ROUTES_PANE, visible);
}

// Hides the boats, the followed one too; what they sailed stays. A popup may hang on the followed boat.
export function setBoatsVisible(mapState, visible) {
  setPaneVisible(mapState, BOATS_PANE, visible);
}

function setPaneVisible(mapState, pane, visible) {
  mapState.map.getPane(pane).style.display = visible ? "" : "none";
  if (!visible) mapState.map.closePopup();
}

export function clearFollowedRoute(mapState) {
  mapState.redrawing = true;
  mapState.followedRouteLayer.clearLayers();
  mapState.redrawing = false;
  mapState.openPoint = null;
  mapState.fittedExternalId = null;
}

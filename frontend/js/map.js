import { boatColor } from "./boat-color.js";
import { reopenSequence } from "./edit-state.js";
import { legMidpoint, legStyle, positionLabel, shouldFitRoute, tailLeg } from "./time-model.js";

const UNCERTAIN = new Set(["on_land", "no_route"]);
const ROUTE_UNCERTAIN = " — route onzeker";

export function createMap(containerId) {
  const map = L.map(containerId).setView([54.5, 8.0], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const activeBoatsLayer = L.layerGroup().addTo(map);
  const followedRouteLayer = L.layerGroup().addTo(map);

  return { map, activeBoatsLayer, followedRouteLayer, fittedExternalId: null };
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
      L.polyline(leg.path, { ...boatLegStyle(style, leg.status, color), weight: 2, opacity: 0.6, interactive: false }).addTo(
        mapState.activeBoatsLayer,
      );
    }

    const marker = L.circleMarker([boat.lat, boat.lng], {
      radius: 6,
      color,
      fillColor: color,
      fillOpacity: boat.dateApproximate ? APPROXIMATE_FILL : 0.85,
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
// A popup that was open is opened again on the same sequence if that point is still drawn.
export function renderFollowedRoute(mapState, patrol, currentPosition, { fit, onExclude = null, isBusy = () => false }) {
  const reopen = reopenSequence(mapState.openSequence, patrol);
  mapState.openSequence = reopen;
  // Clearing the layer closes the popup; that is not the user closing it.
  mapState.redrawing = true;
  mapState.followedRouteLayer.clearLayers();
  mapState.redrawing = false;

  if (patrol === null) {
    return;
  }

  const layer = mapState.followedRouteLayer;
  const fitPoints = patrol.points.map((point) => [point.lat, point.lng]);
  const color = boatColor(patrol.boat_slug ?? "");

  for (const leg of patrol.legs ?? []) {
    const style = legStyle(leg.status);
    if (style !== null && leg.path) {
      const line = L.polyline(leg.path, { ...boatLegStyle(style, leg.status, color), weight: 3 }).addTo(layer);
      if (leg.status === "suspect") {
        line.bindTooltip(leg.reason);
      }
      fitPoints.push(...leg.path);
    }
    if (UNCERTAIN.has(leg.status)) {
      const midpoint = legMidpoint(leg, patrol);
      if (midpoint !== null) {
        const icon = L.divIcon({ className: "leg-uncertain", html: "?", iconSize: [18, 18] });
        L.marker(midpoint, { icon }).bindTooltip(leg.reason).addTo(layer);
      }
    }
  }

  for (const point of patrol.points) {
    const dot = L.circleMarker([point.lat, point.lng], {
      radius: 3,
      color,
      fillColor: color,
      fillOpacity: 1,
    }).addTo(layer);
    if (dot.bindPopup) {
      dot.bindPopup(() => pointPopup(point, { onExclude, busy: isBusy(point) }));
      dot.on("popupopen", () => {
        mapState.openSequence = point.sequence;
      });
      dot.on("popupclose", () => {
        if (!mapState.redrawing) {
          mapState.openSequence = null;
        }
      });
      if (point.sequence === reopen) {
        dot.openPopup();
      }
    }
  }

  if (currentPosition !== null) {
    L.circleMarker([currentPosition.lat, currentPosition.lng], {
      radius: 8,
      color: "#000000",
      fillColor: color,
      fillOpacity: currentPosition.dateApproximate ? APPROXIMATE_FILL : 1,
    })
      .bindTooltip(
        positionLabel({
          boatNumber: patrol.boat_number,
          positionDate: currentPosition.date,
          dateApproximate: currentPosition.dateApproximate,
        }),
      )
      .addTo(layer);
  }

  if (shouldFitRoute(mapState.fittedExternalId, patrol)) {
    mapState.fittedExternalId = patrol.external_id;
    if (fit) {
      mapState.map.fitBounds(fitPoints, { padding: [40, 40] });
    }
  }
}

export function clearFollowedRoute(mapState) {
  mapState.redrawing = true;
  mapState.followedRouteLayer.clearLayers();
  mapState.redrawing = false;
  mapState.openSequence = null;
  mapState.fittedExternalId = null;
}

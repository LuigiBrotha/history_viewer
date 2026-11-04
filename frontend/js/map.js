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

export function renderActiveBoats(mapState, activeBoats, onBoatClick) {
  mapState.activeBoatsLayer.clearLayers();

  for (const boat of activeBoats) {
    const leg = tailLeg(boat.patrol, boat);
    const style = leg === null ? null : legStyle(leg.status);
    if (style !== null && leg.path) {
      L.polyline(leg.path, { ...style, weight: 2, opacity: 0.6, interactive: false }).addTo(
        mapState.activeBoatsLayer,
      );
    }

    const marker = L.circleMarker([boat.lat, boat.lng], {
      radius: 6,
      color: "#0077cc",
      fillColor: "#0077cc",
      fillOpacity: boat.dateApproximate ? APPROXIMATE_FILL : 0.85,
    });
    const uncertain = leg !== null && UNCERTAIN.has(leg.status);
    marker.bindTooltip(uncertain ? `${positionLabel(boat)}${ROUTE_UNCERTAIN}` : positionLabel(boat));
    marker.on("click", () => onBoatClick(boat.boatSlug));
    marker.addTo(mapState.activeBoatsLayer);
  }
}

// fit is true for user actions (boat selected, date changed). A live update passes
// false: it redraws the route but leaves the user's zoom alone.
export function renderFollowedRoute(mapState, patrol, currentPosition, { fit }) {
  mapState.followedRouteLayer.clearLayers();

  if (patrol === null) {
    return;
  }

  const layer = mapState.followedRouteLayer;
  const fitPoints = patrol.points.map((point) => [point.lat, point.lng]);

  for (const leg of patrol.legs ?? []) {
    const style = legStyle(leg.status);
    if (style !== null && leg.path) {
      const line = L.polyline(leg.path, { ...style, weight: 3 }).addTo(layer);
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
    L.circleMarker([point.lat, point.lng], {
      radius: 3,
      color: "#0077cc",
      fillColor: "#0077cc",
      fillOpacity: 1,
    }).addTo(layer);
  }

  if (currentPosition !== null) {
    L.circleMarker([currentPosition.lat, currentPosition.lng], {
      radius: 8,
      color: "#cc3300",
      fillColor: "#ffcc00",
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
  mapState.followedRouteLayer.clearLayers();
  mapState.fittedExternalId = null;
}

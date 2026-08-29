export function createMap(containerId) {
  const map = L.map(containerId).setView([54.5, 8.0], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const activeBoatsLayer = L.layerGroup().addTo(map);
  const followedRouteLayer = L.layerGroup().addTo(map);

  return { map, activeBoatsLayer, followedRouteLayer };
}

export function renderActiveBoats(mapState, activeBoats, onBoatClick) {
  mapState.activeBoatsLayer.clearLayers();

  for (const boat of activeBoats) {
    const marker = L.circleMarker([boat.lat, boat.lng], {
      radius: 6,
      color: "#0077cc",
      fillColor: "#0077cc",
      fillOpacity: 0.85,
    });
    marker.bindTooltip(boat.boatNumber);
    marker.on("click", () => onBoatClick(boat.boatSlug));
    marker.addTo(mapState.activeBoatsLayer);
  }
}

export function renderFollowedRoute(mapState, patrol, currentPosition) {
  mapState.followedRouteLayer.clearLayers();

  const latLngs = patrol.points.map((point) => [point.lat, point.lng]);
  const polyline = L.polyline(latLngs, { color: "#cc3300", weight: 3 });
  polyline.addTo(mapState.followedRouteLayer);

  if (currentPosition !== null) {
    L.circleMarker([currentPosition.lat, currentPosition.lng], {
      radius: 8,
      color: "#cc3300",
      fillColor: "#ffcc00",
      fillOpacity: 1,
    }).addTo(mapState.followedRouteLayer);
  }

  mapState.map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
}

export function clearFollowedRoute(mapState) {
  mapState.followedRouteLayer.clearLayers();
}

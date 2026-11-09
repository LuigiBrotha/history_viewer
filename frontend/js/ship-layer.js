import { shipStyle, shipTooltip } from "./ship-model.js";

const RADIUS = 4;
const FINGER_RADIUS = 7;
const PANE = "ships";
// Above Leaflet's overlay pane (400: boats and routes), below its marker pane (600: Veldslagen).
const PANE_Z_INDEX = 450;
const COARSE_POINTER = () => globalThis.matchMedia?.("(pointer: coarse)").matches ?? false;

// Draws the ships it is given in their own pane, on top of the boats and routes. Ships without
// a position are never drawn. Clicking one calls `onShipClick` with its newest data.
// SVG, not canvas: a canvas on top would take every mouse event from the routes and boats
// below it, while SVG lets through whatever is not on a ship.
export function createShipLayer(map, { onShipClick = null } = {}) {
  map.createPane(PANE);
  map.getPane(PANE).style.zIndex = PANE_Z_INDEX;
  const renderer = L.svg({ pane: PANE });
  const group = L.layerGroup().addTo(map);
  const markers = new Map();

  function key(ship) {
    return `${ship.ship_external_id}|${ship.boat_slug}|${ship.date}`;
  }

  function signature(ship) {
    return `${ship.lat}|${ship.lng}|${ship.outcome}|${ship.tons}|${ship.name}`;
  }

  return {
    setVisible(visible) {
      map.getPane(PANE).style.display = visible ? "" : "none";
    },
    setShips(ships) {
      const wanted = new Map();
      for (const ship of ships) {
        if (ship.lat != null && ship.lng != null) {
          wanted.set(key(ship), ship);
        }
      }
      for (const [id, entry] of markers) {
        const ship = wanted.get(id);
        if (ship === undefined || signature(ship) !== entry.signature) {
          group.removeLayer(entry.marker);
          markers.delete(id);
        } else {
          entry.ship = ship;
        }
      }
      for (const [id, ship] of wanted) {
        if (markers.has(id)) continue;
        const marker = L.circleMarker([ship.lat, ship.lng], {
          renderer,
          radius: COARSE_POINTER() ? FINGER_RADIUS : RADIUS,
          weight: 1,
          ...shipStyle(ship.outcome),
        });
        marker.bindTooltip(shipTooltip(ship));
        marker.on("click", () => onShipClick?.(markers.get(id).ship));
        group.addLayer(marker);
        markers.set(id, { marker, ship, signature: signature(ship) });
      }
    },
  };
}

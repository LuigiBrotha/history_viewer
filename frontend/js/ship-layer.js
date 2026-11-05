import { shipStyle, shipTooltip } from "./ship-model.js";

const RADIUS = 4;
const HIT_TOLERANCE_PX = 6;

// Draws the ships it is given on a canvas, below the route lines. Ships without a
// position are never drawn. Clicking one calls `onShipClick` with its newest data.
// A map that already has a canvas renderer (the status page) shares it: events only
// reach the topmost canvas, so a second one would hide the tooltips of the ships below it.
export function createShipLayer(map, { onShipClick = null } = {}) {
  const shared = map.options.renderer instanceof L.Canvas ? map.options.renderer : null;
  const renderer = shared ?? L.canvas({ tolerance: HIT_TOLERANCE_PX }).addTo(map);
  const group = L.layerGroup().addTo(map);
  const markers = new Map();

  function key(ship) {
    return `${ship.ship_external_id}|${ship.boat_slug}|${ship.date}`;
  }

  function signature(ship) {
    return `${ship.lat}|${ship.lng}|${ship.outcome}|${ship.tons}|${ship.name}`;
  }

  return {
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
          radius: RADIUS,
          weight: 1,
          ...shipStyle(ship.outcome),
        });
        marker.bindTooltip(shipTooltip(ship));
        marker.on("click", () => onShipClick?.(markers.get(id).ship));
        group.addLayer(marker);
        // Routes drawn later land on top; ones drawn earlier must stay above these.
        marker.bringToBack();
        markers.set(id, { marker, ship, signature: signature(ship) });
      }
    },
  };
}

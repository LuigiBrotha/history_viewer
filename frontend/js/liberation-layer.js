import { liberationStyle, liberationTooltip } from "./liberation-model.js";

const LIBERATIONS_URL = "battles/bevrijdingen.json";
const RADIUS = 4;
const FINGER_RADIUS = 7;
const PANE = "liberations";
// Above Leaflet's overlay pane (400: boats and routes), below the ships (450): a ship stays
// clickable where it lies on a liberated harbour.
const PANE_Z_INDEX = 440;
const COARSE_POINTER = () => globalThis.matchMedia?.("(pointer: coarse)").matches ?? false;

export async function loadLiberations(fetchImpl = fetch) {
  const response = await fetchImpl(LIBERATIONS_URL);
  if (!response.ok) {
    throw new Error(`${LIBERATIONS_URL}: ${response.status}`);
  }
  const liberations = await response.json();
  if (!Array.isArray(liberations)) {
    throw new Error(`${LIBERATIONS_URL}: not a list`);
  }
  return liberations;
}

// Draws the Bevrijdingen it is given ({ key, liberation, state }) in their own pane; places
// without a position are never drawn. SVG for the same reason as the ships: it lets the mouse
// through to the routes between its circles.
export function createLiberationLayer(map, { onLiberationClick = null } = {}) {
  map.createPane(PANE);
  map.getPane(PANE).style.zIndex = PANE_Z_INDEX;
  const renderer = L.svg({ pane: PANE });
  const group = L.layerGroup().addTo(map);
  const markers = new Map();

  function signature({ liberation, state }) {
    return `${state}|${liberation.lat}|${liberation.lng}|${liberation.source}|${liberationTooltip(liberation)}`;
  }

  return {
    setVisible(visible) {
      map.getPane(PANE).style.display = visible ? "" : "none";
    },
    setLiberations(items) {
      const wanted = new Map();
      for (const item of items) {
        if (item.liberation.lat != null && item.liberation.lng != null) {
          wanted.set(item.key, item);
        }
      }
      for (const [key, entry] of markers) {
        const item = wanted.get(key);
        if (item === undefined || signature(item) !== entry.signature) {
          group.removeLayer(entry.marker);
          markers.delete(key);
        } else {
          entry.liberation = item.liberation;
        }
      }
      for (const [key, item] of wanted) {
        if (markers.has(key)) continue;
        const { liberation, state } = item;
        const marker = L.circleMarker([liberation.lat, liberation.lng], {
          renderer,
          radius: COARSE_POINTER() ? FINGER_RADIUS : RADIUS,
          ...liberationStyle(state, liberation),
        });
        marker.bindTooltip(liberationTooltip(liberation));
        marker.on("click", () => onLiberationClick?.(markers.get(key).liberation));
        group.addLayer(marker);
        markers.set(key, { marker, liberation, signature: signature(item) });
      }
    },
  };
}

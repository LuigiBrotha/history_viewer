// Plaatshints: the places the articles of the selected Veldslag name, drawn as triangles with
// their name, unlike the squares, circles and lines of the other data. The infobox's places are
// drawn in the accent colour, the text's in ink. A click on one while placing moves the square there.

const HINT_SIZE = 14;
const MAX_ZOOM = 8;

// [[south, west], [north, east]] around the hints.
export function hintBounds(hints) {
  const lats = hints.map((h) => h.lat);
  const lngs = hints.map((h) => h.lng);
  return [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]];
}

const EARTH_KM = 6371;
const toRad = (degrees) => (degrees * Math.PI) / 180;

function distanceKm(a, b) {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.sqrt(Math.min(1, h)));
}

// The middle of points on the globe: the mean of their unit vectors.
function middle(points) {
  let x = 0;
  let y = 0;
  let z = 0;
  for (const { lat, lng } of points) {
    x += Math.cos(toRad(lat)) * Math.cos(toRad(lng));
    y += Math.cos(toRad(lat)) * Math.sin(toRad(lng));
    z += Math.sin(toRad(lat));
  }
  return { lat: (Math.atan2(z, Math.hypot(x, y)) * 180) / Math.PI, lng: (Math.atan2(y, x) * 180) / Math.PI };
}

// How the chosen position of a battle relates to the places its articles name: offsetKm, the
// distance from the middle of the hints (null without a position), and spreadKm, the standard
// deviation of the hints around that middle. Null without hints.
export function placeStats(battle, hints) {
  if (!hints?.length) return null;
  const centre = middle(hints);
  const spreadKm = Math.sqrt(hints.reduce((sum, h) => sum + distanceKm(h, centre) ** 2, 0) / hints.length);
  const placed = battle.lat != null && battle.lng != null;
  return { count: hints.length, offsetKm: placed ? distanceKm(battle, centre) : null, spreadKm };
}

export function placeStatsText(stats) {
  if (!stats) return "";
  const spread = `spreiding ${Math.round(stats.spreadKm)} km`;
  const places = `${stats.count} Plaatshint${stats.count === 1 ? "" : "s"}`;
  if (stats.offsetKm === null) return `${places} · ${spread}`;
  return `Positie ${Math.round(stats.offsetKm)} km van het midden van ${places} · ${spread}`;
}

function hintIcon(hint) {
  const root = document.createElement("span");
  const triangle = document.createElement("span");
  triangle.className = "place-hint-triangle";
  const name = document.createElement("span");
  name.className = "place-hint-name";
  name.textContent = hint.name;
  root.append(triangle, name);
  return L.divIcon({ className: `place-hint ${hint.kind}`, iconSize: [HINT_SIZE, HINT_SIZE], html: root });
}

export function createHintLayer(map, { onPick } = {}) {
  const group = L.layerGroup().addTo(map);
  let drawn = [];

  function clear() {
    drawn.forEach((marker) => group.removeLayer(marker));
    drawn = [];
  }

  return {
    // Draws these hints (replacing any others); with fit, shows them all, zoomed in no further than 8.
    show(hints, { fit = true } = {}) {
      clear();
      for (const hint of hints ?? []) {
        const marker = L.marker([hint.lat, hint.lng], {
          icon: hintIcon(hint), keyboard: false, zIndexOffset: 500, title: hint.name,
        });
        marker.on("click", () => onPick?.(hint));
        group.addLayer(marker);
        drawn.push(marker);
      }
      if (fit && drawn.length > 0) map.fitBounds(hintBounds(hints), { maxZoom: MAX_ZOOM, padding: [48, 48] });
    },
    clear,
  };
}

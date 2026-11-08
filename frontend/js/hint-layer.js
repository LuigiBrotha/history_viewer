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

// How a battle's position lies among the places its articles name, from the summary of its
// Plaatshints ({ count, lat, lng, spread_km }: their middle and spread): "42 km van 9 plaatsen ·
// spreiding 120 km", or without a position only the count and spread; "" without hints.
export function placeText(battle, summary) {
  if (!summary) return "";
  const places = `${summary.count} ${summary.count === 1 ? "plaats" : "plaatsen"}`;
  const spread = `spreiding ${Math.round(summary.spread_km)} km`;
  if (battle.lat == null || battle.lng == null) return `${places} · ${spread}`;
  return `${Math.round(distanceKm(battle, summary))} km van ${places} · ${spread}`;
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

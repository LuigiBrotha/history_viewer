// Plaatshints: the places the articles of a Veldslag without a position link to, drawn as
// rings with their name when that battle is selected. The infobox's places are drawn in the
// accent colour, the text's in ink. A click on one while placing moves the square there.

const HINT_SIZE = 14;
const MAX_ZOOM = 8;

// [[south, west], [north, east]] around the hints.
export function hintBounds(hints) {
  const lats = hints.map((h) => h.lat);
  const lngs = hints.map((h) => h.lng);
  return [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]];
}

function hintIcon(hint) {
  const root = document.createElement("span");
  const ring = document.createElement("span");
  ring.className = "place-hint-ring";
  const name = document.createElement("span");
  name.className = "place-hint-name";
  name.textContent = hint.name;
  root.append(ring, name);
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
    // Draws these hints (replacing any others) and shows them all, zoomed in no further than 8.
    show(hints) {
      clear();
      for (const hint of hints ?? []) {
        const marker = L.marker([hint.lat, hint.lng], {
          icon: hintIcon(hint), keyboard: false, zIndexOffset: 500, title: hint.name,
        });
        marker.on("click", () => onPick?.(hint));
        group.addLayer(marker);
        drawn.push(marker);
      }
      if (drawn.length > 0) map.fitBounds(hintBounds(hints), { maxZoom: MAX_ZOOM, padding: [48, 48] });
    },
    clear,
  };
}

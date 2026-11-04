const OVERLAY_OPACITY = 0.5;
const PANE = "atlas";
// Above the base map, below the route lines and markers.
const PANE_Z_INDEX = 350;

export function atlasMapFor(maps, isoDate) {
  let found = null;
  for (const entry of maps) {
    if (entry.date <= isoDate) {
      found = entry;
    }
  }
  return found;
}

function addLegend(map, legend, labelEl) {
  const control = L.control({ position: "bottomleft" });
  control.onAdd = () => {
    const box = L.DomUtil.create("div", "atlas-legend");
    box.append(labelEl);
    for (const { name, color } of legend) {
      const row = document.createElement("div");
      const swatch = document.createElement("span");
      swatch.className = "atlas-swatch";
      swatch.style.background = color;
      row.append(swatch, name);
      box.append(row);
    }
    return box;
  };
  control.addTo(map);
}

// Shows the historical map belonging to a date. Without its manifest the page simply
// goes on without a historical layer.
export async function initAtlas(map) {
  let manifest;
  try {
    const response = await fetch("atlas/manifest.json");
    if (!response.ok) {
      throw new Error(`Failed to fetch atlas: ${response.status}`);
    }
    manifest = await response.json();
  } catch (error) {
    console.error(error);
    return { setDate() {} };
  }

  map.createPane(PANE);
  map.getPane(PANE).style.zIndex = PANE_Z_INDEX;
  map.getPane(PANE).style.pointerEvents = "none";

  const labelEl = document.createElement("div");
  labelEl.className = "atlas-label";
  addLegend(map, manifest.legend, labelEl);

  let current; // undefined until the first date: "no map" must also get its label.
  let overlay = null;
  return {
    setDate(isoDate) {
      const entry = atlasMapFor(manifest.maps, isoDate);
      if (entry === current) {
        return;
      }
      current = entry;
      if (overlay !== null) {
        map.removeLayer(overlay);
        overlay = null;
      }
      labelEl.textContent = entry === null ? "Geen historische kaart" : `Kaart: ${entry.label}`;
      if (entry !== null) {
        overlay = L.imageOverlay(entry.file, manifest.bounds, {
          pane: PANE,
          opacity: OVERLAY_OPACITY,
          interactive: false,
          attribution: `Historische kaart: <a href="${entry.source}">Wikimedia Commons</a>, CC BY-SA 3.0, bewerkt`,
        }).addTo(map);
      }
    },
  };
}

import { dutchMapLayer } from "./dutch-map.js";

const STORAGE_KEY = "uboats.baseMap";
const DEFAULT_MAP = "Oceaandiepte";

export const BASE_MAPS = {
  Straatkaart: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: { maxZoom: 12, attribution: "&copy; OpenStreetMap contributors" },
  },
  Oceaandiepte: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
    // Deeper zoom levels of this map have gaps over open ocean, so those are enlarged instead.
    options: {
      maxZoom: 12,
      maxNativeZoom: 10,
      attribution: "Dieptekaart: Esri, Garmin, GEBCO, NOAA NGDC en anderen",
    },
  },
  // Vector tiles with Dutch place, country, river and sea names; MapLibre loads only when chosen.
  "Nederlandse namen": { vector: dutchMapLayer },
};

export function savedBaseMap(storage) {
  try {
    const name = storage.getItem(STORAGE_KEY);
    return Object.hasOwn(BASE_MAPS, name ?? "") ? name : DEFAULT_MAP;
  } catch {
    return DEFAULT_MAP;
  }
}

export function addBaseMaps(map, storage = globalThis.localStorage) {
  const layers = {};
  for (const [name, { url, options, vector }] of Object.entries(BASE_MAPS)) {
    layers[name] = vector ? vector() : L.tileLayer(url, options);
  }
  layers[savedBaseMap(storage)].addTo(map);
  L.control.layers(layers, null, { position: "topleft", collapsed: true }).addTo(map);
  map.on("baselayerchange", ({ name }) => {
    try {
      storage.setItem(STORAGE_KEY, name);
    } catch {
      // Not being remembered is no reason to fail.
    }
  });
}

// A world map with Dutch names: OpenFreeMap's vector tiles, drawn by MapLibre inside Leaflet.
// MapLibre is large, so it is only fetched once someone picks this map.

export const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
export const MAPLIBRE_CSS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";
export const MAPLIBRE_JS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js";
export const MAPLIBRE_LEAFLET_JS = "https://unpkg.com/@maplibre/maplibre-gl-leaflet@0.0.22/leaflet-maplibre-gl.js";

const ATTRIBUTION =
  '<a href="https://openfreemap.org">OpenFreeMap</a> &copy; <a href="https://www.openmaptiles.org/">OpenMapTiles</a>, ' +
  'gegevens &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-bijdragers';

// Dutch where OpenStreetMap has it; otherwise the name in Latin letters, so that a Russian
// village stays readable; the local name as the last resort.
export const DUTCH_NAME = ["coalesce", ["get", "name:nl"], ["get", "name:latin"], ["get", "name_int"], ["get", "name"]];

function showsName(textField) {
  if (typeof textField === "string") return /\{name/.test(textField);
  return /\["get","name/.test(JSON.stringify(textField ?? null));
}

export function withDutchNames(style) {
  const layers = style.layers.map((layer) =>
    layer.type === "symbol" && showsName(layer.layout?.["text-field"])
      ? { ...layer, layout: { ...layer.layout, "text-field": DUTCH_NAME } }
      : layer,
  );
  return { ...style, layers };
}

function inject(doc, tag, attributes) {
  return new Promise((resolve, reject) => {
    const node = Object.assign(doc.createElement(tag), attributes);
    node.onload = resolve;
    node.onerror = () => reject(new Error(`Kon ${attributes.src ?? attributes.href} niet laden`));
    doc.head.appendChild(node);
  });
}

const loading = new WeakMap();

export function loadMapLibre(doc = globalThis.document) {
  if (!loading.has(doc)) {
    // The style sheet only affects looks: no need to wait for it.
    inject(doc, "link", { rel: "stylesheet", href: MAPLIBRE_CSS }).catch(() => {});
    const scripts = inject(doc, "script", { src: MAPLIBRE_JS })
      .then(() => inject(doc, "script", { src: MAPLIBRE_LEAFLET_JS }))
      .catch((error) => {
        loading.delete(doc);
        throw error;
      });
    loading.set(doc, scripts);
  }
  return loading.get(doc);
}

async function fetchDutchStyle() {
  const response = await fetch(STYLE_URL);
  if (!response.ok) throw new Error(`Kon de kaartstijl niet laden: ${response.status}`);
  return response.json();
}

// A stand-in layer for the layer switch: it fetches MapLibre and the style when it is added,
// then puts the real MapLibre layer in the tile pane, under every overlay.
export function dutchMapLayer({ load = loadMapLibre, fetchStyle = fetchDutchStyle } = {}) {
  const DutchMap = L.Layer.extend({
    options: { maxZoom: 12, attribution: ATTRIBUTION },

    beforeAdd(map) {
      // Like a tile layer, so the map does not zoom in further than the other backgrounds.
      map._addZoomLimit?.(this);
    },

    onAdd(map) {
      const turn = (this._turn = (this._turn ?? 0) + 1);
      Promise.all([load(), fetchStyle()])
        .then(([, style]) => {
          if (this._turn !== turn || this._map !== map) return;
          this._gl = L.maplibreGL({ style: withDutchNames(style) }).addTo(map);
        })
        .catch((error) => console.error(error));
    },

    onRemove() {
      this._turn = (this._turn ?? 0) + 1;
      this._gl?.remove();
      this._gl = null;
    },
  });
  return new DutchMap();
}

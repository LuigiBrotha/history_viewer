import { test } from "node:test";
import assert from "node:assert/strict";

import { DUTCH_NAME, MAPLIBRE_CSS, MAPLIBRE_JS, MAPLIBRE_LEAFLET_JS, dutchMapLayer, loadMapLibre, withDutchNames } from "../js/dutch-map.js";

const OSM_LIBERTY_NAME = [
  "case",
  ["has", "name:nonlatin"],
  ["concat", ["get", "name:latin"], "\n", ["get", "name:nonlatin"]],
  ["coalesce", ["get", "name_en"], ["get", "name"]],
];

function style(...layers) {
  return { version: 8, sources: {}, layers };
}

test("labels show the Dutch name first, then the Latin, international and local name", () => {
  assert.deepEqual(DUTCH_NAME, [
    "coalesce",
    ["get", "name:nl"],
    ["get", "name:latin"],
    ["get", "name_int"],
    ["get", "name"],
  ]);
});

test("withDutchNames rewrites every label that shows a name", () => {
  const original = style(
    { id: "label_city", type: "symbol", layout: { "text-field": OSM_LIBERTY_NAME, "text-size": 12 } },
    { id: "water_name", type: "symbol", layout: { "text-field": "{name:latin}\n{name:nonlatin}" } },
    { id: "river", type: "symbol", layout: { "text-field": ["get", "name"] } },
  );

  const dutch = withDutchNames(original);

  assert.deepEqual(
    dutch.layers.map((layer) => layer.layout["text-field"]),
    [DUTCH_NAME, DUTCH_NAME, DUTCH_NAME],
  );
  assert.equal(dutch.layers[0].layout["text-size"], 12);
});

test("withDutchNames leaves road numbers, icons and other layers alone", () => {
  const shield = { id: "shield", type: "symbol", layout: { "text-field": ["to-string", ["get", "ref"]] } };
  const icon = { id: "icon", type: "symbol", layout: { "icon-image": "airport" } };
  const water = { id: "water", type: "fill", paint: { "fill-color": "#cde" } };

  const dutch = withDutchNames(style(shield, icon, water));

  assert.deepEqual(dutch.layers, [shield, icon, water]);
});

test("withDutchNames does not change the style it was given", () => {
  const original = style({ id: "label", type: "symbol", layout: { "text-field": ["get", "name"] } });

  withDutchNames(original);

  assert.deepEqual(original.layers[0].layout["text-field"], ["get", "name"]);
});

function fakeDocument() {
  const appended = [];
  return {
    appended,
    createElement: (tag) => ({ tag }),
    head: {
      appendChild(node) {
        appended.push(node);
        return node;
      },
    },
  };
}

test("loadMapLibre loads MapLibre's style sheet and script, then the Leaflet bridge, once", async () => {
  const doc = fakeDocument();

  const loading = loadMapLibre(doc);
  assert.deepEqual(
    doc.appended.map((node) => node.href ?? node.src),
    [MAPLIBRE_CSS, MAPLIBRE_JS],
  );
  doc.appended[1].onload();
  await Promise.resolve();
  assert.equal(doc.appended[2].src, MAPLIBRE_LEAFLET_JS);
  doc.appended[2].onload();
  await loading;

  assert.equal(loadMapLibre(doc), loading);
  assert.equal(doc.appended.length, 3);
});

test("the scripts are pinned to an exact version", () => {
  assert.match(MAPLIBRE_JS, /maplibre-gl@\d+\.\d+\.\d+\//);
  assert.match(MAPLIBRE_CSS, /maplibre-gl@\d+\.\d+\.\d+\//);
  assert.match(MAPLIBRE_LEAFLET_JS, /maplibre-gl-leaflet@\d+\.\d+\.\d+\//);
});

test("a failed load is tried again next time", async () => {
  const doc = fakeDocument();

  const first = loadMapLibre(doc);
  doc.appended.at(-1).onerror();
  await assert.rejects(first);

  assert.notEqual(loadMapLibre(doc), first);
});

function fakeLeaflet() {
  const created = [];
  globalThis.L = {
    Layer: {
      extend(methods) {
        return function Layer(options) {
          Object.assign(this, methods);
          this.options = { ...methods.options, ...options };
        };
      },
    },
    maplibreGL(options) {
      const layer = {
        options,
        onMap: null,
        addTo(map) {
          layer.onMap = map;
          return layer;
        },
        remove() {
          layer.onMap = null;
        },
      };
      created.push(layer);
      return layer;
    },
  };
  return created;
}

const STYLE = style({ id: "label", type: "symbol", layout: { "text-field": ["get", "name"] } });

function addTo(layer, map) {
  layer._map = map;
  layer.beforeAdd?.(map);
  layer.onAdd(map);
}

function removeFrom(layer, map) {
  layer.onRemove(map);
  layer._map = null;
}

test("the Dutch map draws MapLibre with Dutch labels once it is on the map", async () => {
  const created = fakeLeaflet();
  const map = { limited: [], _addZoomLimit(layer) { this.limited.push(layer); } };
  const layer = dutchMapLayer({ load: async () => {}, fetchStyle: async () => STYLE });

  addTo(layer, map);
  await new Promise(setImmediate);

  assert.equal(created.length, 1);
  assert.equal(created[0].onMap, map);
  assert.deepEqual(created[0].options.style.layers[0].layout["text-field"], DUTCH_NAME);
  assert.deepEqual(map.limited, [layer]);
  assert.match(layer.options.attribution, /OpenFreeMap/);
  assert.match(layer.options.attribution, /OpenMapTiles/);
  assert.match(layer.options.attribution, /OpenStreetMap/);
});

test("switching away removes MapLibre, switching back shows it again", async () => {
  const created = fakeLeaflet();
  const map = {};
  const layer = dutchMapLayer({ load: async () => {}, fetchStyle: async () => STYLE });

  addTo(layer, map);
  await new Promise(setImmediate);
  removeFrom(layer, map);
  assert.equal(created[0].onMap, null);

  addTo(layer, map);
  await new Promise(setImmediate);
  assert.equal(created.at(-1).onMap, map);
});

test("a map switched away before MapLibre arrived is not drawn", async () => {
  const created = fakeLeaflet();
  const map = {};
  const layer = dutchMapLayer({ load: async () => {}, fetchStyle: async () => STYLE });

  addTo(layer, map);
  removeFrom(layer, map);
  await new Promise(setImmediate);

  assert.equal(created.filter((gl) => gl.onMap).length, 0);
});

test("a failing download leaves the map without background, not broken", async () => {
  fakeLeaflet();
  const errors = [];
  const originalError = console.error;
  console.error = (error) => errors.push(error);
  try {
    const layer = dutchMapLayer({ load: async () => {}, fetchStyle: async () => { throw new Error("offline"); } });
    addTo(layer, {});
    await new Promise(setImmediate);
  } finally {
    console.error = originalError;
  }
  assert.equal(errors.length, 1);
});

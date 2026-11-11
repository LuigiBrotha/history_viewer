import { test } from "node:test";
import assert from "node:assert/strict";

import { BASE_MAPS, addBaseMaps, savedBaseMap } from "../js/base-maps.js";

function fakeStorage(value = null) {
  return {
    saved: value,
    getItem() {
      return this.saved;
    },
    setItem(_, next) {
      this.saved = next;
    },
  };
}

function fakeLeaflet() {
  const added = [];
  const controls = [];
  globalThis.L = {
    Layer: {
      extend(methods) {
        return function Layer() {
          Object.assign(this, methods);
          this.options = { ...methods.options };
          this.addTo = () => {
            added.push("vector");
            return this;
          };
        };
      },
    },
    tileLayer: (url, options) => {
      const layer = {
        url,
        options,
        addTo() {
          added.push(url);
          return layer;
        },
      };
      return layer;
    },
    control: {
      layers: (layers) => ({
        addTo() {
          controls.push(Object.keys(layers));
        },
      }),
    },
  };
  return { added, controls };
}

function fakeMap() {
  const handlers = {};
  return {
    handlers,
    on(event, handler) {
      handlers[event] = handler;
    },
  };
}

test("savedBaseMap falls back on the depth map", () => {
  assert.equal(savedBaseMap(fakeStorage()), "Oceaandiepte");
  assert.equal(savedBaseMap(fakeStorage("bestaat niet")), "Oceaandiepte");
  assert.equal(savedBaseMap(fakeStorage("Straatkaart")), "Straatkaart");
});

test("savedBaseMap survives blocked storage", () => {
  const blocked = {
    getItem() {
      throw new Error("blocked");
    },
  };
  assert.equal(savedBaseMap(blocked), "Oceaandiepte");
});

test("the depth map credits its sources and does not ask for tiles that don't exist", () => {
  const { options, url } = BASE_MAPS.Oceaandiepte;
  assert.match(url, /Ocean\/World_Ocean_Base/);
  assert.match(options.attribution, /GEBCO/);
  assert.ok(options.maxNativeZoom <= 10);
  assert.ok(options.maxZoom >= options.maxNativeZoom);
});

test("addBaseMaps shows the saved map and offers all three", () => {
  const { added, controls } = fakeLeaflet();

  addBaseMaps(fakeMap(), fakeStorage("Oceaandiepte"));

  assert.deepEqual(added, [BASE_MAPS.Oceaandiepte.url]);
  assert.deepEqual(controls, [["Straatkaart", "Oceaandiepte", "Nederlandse namen"]]);
});

test("the map with Dutch names can be the saved choice", () => {
  const { added } = fakeLeaflet();

  assert.equal(savedBaseMap(fakeStorage("Nederlandse namen")), "Nederlandse namen");
  addBaseMaps(fakeMap(), fakeStorage("Nederlandse namen"));

  assert.deepEqual(added, ["vector"]);
});

test("a choice is remembered", () => {
  fakeLeaflet();
  const map = fakeMap();
  const storage = fakeStorage();

  addBaseMaps(map, storage);
  map.handlers.baselayerchange({ name: "Oceaandiepte" });

  assert.equal(storage.saved, "Oceaandiepte");
});

test("a failing store does not break the choice", () => {
  fakeLeaflet();
  const map = fakeMap();
  const storage = {
    getItem: () => null,
    setItem() {
      throw new Error("full");
    },
  };

  addBaseMaps(map, storage);

  assert.doesNotThrow(() => map.handlers.baselayerchange({ name: "Oceaandiepte" }));
});

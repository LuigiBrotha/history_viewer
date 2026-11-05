import { test } from "node:test";
import assert from "node:assert/strict";

import { createBattleLayer } from "../js/battle-layer.js";
import { installFakeDom } from "./fake-dom.js";

const battle = (over = {}) => ({
  title: "Battle of Kursk",
  start: "1943-07-05",
  end: "1943-08-23",
  precision: "day",
  date_text: "5 July – 23 August 1943",
  lat: 51.7,
  lng: 36.1,
  part_of: null,
  place: null,
  ...over,
});

function setup({ zoom = 5, bounds = { south: -90, west: -180, north: 90, east: 180 } } = {}) {
  installFakeDom();
  const layers = new Set();
  const handlers = {};
  const pans = [];
  globalThis.L = {
    divIcon: (options) => ({ ...options }),
    marker: (latlng, options) => {
      const marker = {
        latlng,
        options,
        events: {},
        on(type, fn) {
          marker.events[type] = fn;
          return marker;
        },
        bindTooltip(content, tooltipOptions) {
          marker.tooltip = { content, options: tooltipOptions };
          return marker;
        },
        setIcon(icon) {
          marker.options = { ...marker.options, icon };
        },
      };
      return marker;
    },
    layerGroup: () => ({
      addTo() {
        return this;
      },
      addLayer: (layer) => layers.add(layer),
      removeLayer: (layer) => layers.delete(layer),
    }),
  };
  const map = {
    on: (types, fn) => {
      for (const type of types.split(" ")) handlers[type] = fn;
    },
    getZoom: () => map.zoom,
    getBounds: () => ({
      getSouth: () => map.bounds.south,
      getWest: () => map.bounds.west,
      getNorth: () => map.bounds.north,
      getEast: () => map.bounds.east,
    }),
    panTo: (latlng) => pans.push(latlng),
    zoom,
    bounds,
  };
  const clicks = [];
  const layer = createBattleLayer(map, { onBattleClick: (b) => clicks.push(b) });
  const squares = () => [...layers].filter((m) => m.options.icon.className.includes("battle-square"));
  const labels = () => [...layers].filter((m) => m.options.icon.className.includes("battle-label"));
  return { layer, map, handlers, clicks, pans, squares, labels };
}

test("each battle with a position becomes a small square marker", () => {
  const { layer, squares } = setup();
  layer.setBattles([battle(), battle({ title: "Atlantic", lat: null, lng: null })]);
  assert.equal(squares().length, 1);
  const [marker] = squares();
  assert.deepEqual(marker.latlng, [51.7, 36.1]);
  assert.equal(marker.options.icon.className, "battle-square");
  assert.deepEqual(marker.options.icon.iconSize, [10, 10]);
  assert.equal(marker.options.keyboard, false);
});

test("the tooltip shows name, dates and duration as text nodes", () => {
  const { layer, squares } = setup();
  layer.setBattles([battle({ title: "<img src=x onerror=alert(1)>" })]);
  const content = squares()[0].tooltip.content;
  const texts = content.children.map((child) => child.textContent);
  assert.deepEqual(texts, ["<img src=x onerror=alert(1)>", "5 July – 23 August 1943", "50 dagen"]);
});

test("the icon html is a node, never a string built from source data", () => {
  const { layer, squares, labels } = setup();
  layer.setBattles([battle({ title: "<b>x</b>" })]);
  assert.equal(typeof squares()[0].options.icon.html, "object");
  const label = labels()[0].options.icon.html;
  assert.equal(typeof label, "object");
  assert.equal(label.textContent, "<b>x</b>");
});

test("a click on a square reports the battle", () => {
  const { layer, squares, clicks } = setup();
  const kursk = battle();
  layer.setBattles([kursk]);
  squares()[0].events.click();
  assert.deepEqual(clicks, [kursk]);
});

test("setBattles replaces what was drawn and keeps squares that stay", () => {
  const { layer, squares } = setup();
  layer.setBattles([battle({ title: "a" }), battle({ title: "b" })]);
  const [first] = squares();
  layer.setBattles([battle({ title: "a" })]);
  assert.equal(squares().length, 1);
  assert.equal(squares()[0], first);
  layer.setBattles([]);
  assert.equal(squares().length, 0);
});

test("only battles in view are drawn and the map redraws when it moves or zooms", () => {
  const { layer, map, handlers, squares } = setup({ bounds: { south: 40, west: 30, north: 60, east: 50 } });
  layer.setBattles([battle({ title: "in" }), battle({ title: "out", lat: -30, lng: 20 })]);
  assert.deepEqual(squares().map((m) => m.options.battleTitle), ["in"]);

  map.bounds = { south: -60, west: 0, north: -10, east: 40 };
  handlers.moveend();
  assert.deepEqual(squares().map((m) => m.options.battleTitle), ["out"]);

  map.bounds = { south: -90, west: -180, north: 90, east: 180 };
  handlers.zoomend();
  assert.equal(squares().length, 2);
});

test("no more than 1500 squares are drawn, the longest first", () => {
  const { layer, squares } = setup();
  const many = Array.from({ length: 1505 }, (_, i) => battle({ title: `b${i}`, end: i < 5 ? "1943-07-05" : "1943-08-23" }));
  layer.setBattles(many);
  assert.equal(squares().length, 1500);
  assert.ok(!squares().some((m) => ["b0", "b1", "b2", "b3", "b4"].includes(m.options.battleTitle)));
});

test("names show next to few squares, or when zoomed in", () => {
  const many = Array.from({ length: 30 }, (_, i) => battle({ title: `b${i}` }));
  const { layer, map, handlers, labels } = setup({ zoom: 4 });
  layer.setBattles(many);
  assert.equal(labels().length, 0);
  map.zoom = 6;
  handlers.zoomend();
  assert.equal(labels().length, 30);
  assert.equal(labels()[0].options.interactive, false);
  layer.setBattles(many.slice(0, 3));
  map.zoom = 3;
  handlers.zoomend();
  assert.equal(labels().length, 3);
});

test("setSelected marks one square and showBattle pans to it", () => {
  const { layer, squares, pans } = setup();
  const kursk = battle();
  layer.setBattles([kursk, battle({ title: "other", lat: 10, lng: 10 })]);
  layer.setSelected(kursk);
  const classes = Object.fromEntries(squares().map((m) => [m.options.battleTitle, m.options.icon.className]));
  assert.equal(classes["Battle of Kursk"], "battle-square selected");
  assert.equal(classes.other, "battle-square");
  layer.setSelected(null);
  assert.ok(squares().every((m) => m.options.icon.className === "battle-square"));

  layer.showBattle(kursk);
  assert.deepEqual(pans, [[51.7, 36.1]]);
  layer.showBattle(battle({ lat: null, lng: null }));
  assert.equal(pans.length, 1);
});

test("a battle past the date line appears in the copy of the world that is in view", () => {
  const { layer, squares, labels } = setup({ zoom: 7, bounds: { south: -45, west: 100, north: 62, east: 260 } });
  layer.setBattles([battle({ title: "Pearl Harbor", lat: 21.4, lng: -157.9 })]);
  assert.deepEqual(squares()[0].latlng, [21.4, 202.1]);
  assert.deepEqual(labels()[0].latlng, [21.4, 202.1]);
});

test("a square moves back when the map returns to the other side of the date line", () => {
  const { layer, map, handlers, squares } = setup({ bounds: { south: -45, west: 100, north: 62, east: 260 } });
  layer.setBattles([battle({ title: "Pearl Harbor", lat: 21.4, lng: -157.9 })]);
  map.bounds = { south: -60, west: -180, north: 80, east: 0 };
  handlers.moveend();
  assert.deepEqual(squares()[0].latlng, [21.4, -157.9]);
});

test("showBattle pans to the copy of the battle nearest to the view", () => {
  const { layer, pans } = setup({ bounds: { south: -45, west: 100, north: 62, east: 260 } });
  layer.showBattle(battle({ lat: 21.4, lng: -157.9 }));
  assert.deepEqual(pans, [[21.4, 202.1]]);
});

test("a battle gets a square in every copy of the world in view, as the base map repeats", () => {
  const { layer, squares } = setup({ bounds: { south: -60, west: -300, north: 80, east: 300 } });
  layer.setBattles([battle({ title: "Pearl Harbor", lat: 21.4, lng: -157.9 })]);
  assert.deepEqual(squares().map((m) => m.latlng).sort((a, b) => a[1] - b[1]), [[21.4, -157.9], [21.4, 202.1]]);
});

test("selecting a battle marks its square in every copy", () => {
  const { layer, squares } = setup({ bounds: { south: -60, west: -300, north: 80, east: 300 } });
  const pearl = battle({ title: "Pearl Harbor", lat: 21.4, lng: -157.9 });
  layer.setBattles([pearl]);
  layer.setSelected(pearl);
  assert.deepEqual(squares().map((m) => m.options.icon.className), ["battle-square selected", "battle-square selected"]);
});

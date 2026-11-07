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
        getLatLng: () => marker.dragged ?? { lat: marker.latlng[0], lng: marker.latlng[1] },
        dragging: {
          on: false,
          enable() {
            marker.dragging.on = true;
          },
          disable() {
            marker.dragging.on = false;
          },
          enabled: () => marker.dragging.on,
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
    setView: (latlng, nextZoom) => pans.push([...latlng, nextZoom]),
    getCenter: () => ({ lat: 12, lng: 34 }),
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

test("every battle in view gets a square, also when there are many", () => {
  const { layer, squares } = setup();
  const many = Array.from({ length: 900 }, (_, i) => battle({ title: `b${i}` }));
  layer.setBattles(many);
  assert.equal(squares().length, 900);
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

test("setSelected marks one square and showBattle zooms in to it", () => {
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
  assert.deepEqual(pans, [[51.7, 36.1, 8]]);
  layer.showBattle(battle({ lat: null, lng: null }));
  assert.equal(pans.length, 1);
});

test("showBattle never zooms out", () => {
  const { layer, pans } = setup({ zoom: 11 });
  layer.showBattle(battle());
  assert.deepEqual(pans, [[51.7, 36.1, 11]]);
});

test("a battle with an own position gets the own class, also when selected", () => {
  const { layer, squares } = setup();
  const own = battle({ own: true });
  layer.setBattles([own, battle({ title: "other" })]);
  const classes = Object.fromEntries(squares().map((m) => [m.options.battleTitle, m.options.icon.className]));
  assert.ok(classes["Battle of Kursk"].split(" ").includes("own"));
  assert.equal(classes.other, "battle-square");
  layer.setSelected(own);
  assert.equal(squares()[0].options.icon.className, "battle-square own selected");
});

test("startEdit makes only that battle's square draggable", () => {
  const { layer, squares } = setup();
  const kursk = battle();
  layer.setBattles([kursk, battle({ title: "other", lat: 10, lng: 10 })]);
  layer.startEdit(kursk, { onMove() {} });
  const enabled = Object.fromEntries(squares().map((m) => [m.options.battleTitle, m.dragging.on]));
  assert.deepEqual(enabled, { "Battle of Kursk": true, other: false });
});

test("startEdit on a battle without a position puts a square at the map centre", () => {
  const { layer, squares } = setup();
  const atlantic = battle({ title: "Atlantic", lat: null, lng: null });
  layer.setBattles([atlantic]);
  assert.equal(squares().length, 0);
  const edit = layer.startEdit(atlantic, { onMove() {} });
  assert.equal(squares().length, 1);
  assert.deepEqual(squares()[0].latlng, [12, 34]);
  assert.equal(squares()[0].dragging.on, true);
  assert.deepEqual(edit.position(), { lat: 12, lng: 34 });
});

test("a drag past the date line is wrapped for position() and onMove", () => {
  const { layer, squares } = setup();
  const kursk = battle();
  layer.setBattles([kursk]);
  const moves = [];
  const edit = layer.startEdit(kursk, { onMove: (p) => moves.push(p) });
  squares()[0].dragged = { lat: 20, lng: 190 };
  squares()[0].events.dragend();
  assert.deepEqual(edit.position(), { lat: 20, lng: -170 });
  assert.deepEqual(moves, [{ lat: 20, lng: -170 }]);
});

test("the edited square survives setBattles and a move out of view", () => {
  const { layer, map, handlers, squares } = setup();
  const kursk = battle();
  layer.setBattles([kursk]);
  layer.startEdit(kursk, { onMove() {} });
  layer.setBattles([]);
  assert.equal(squares().length, 1);
  map.bounds = { south: -60, west: 0, north: -10, east: 40 };
  handlers.moveend();
  assert.equal(squares().length, 1);
  assert.equal(squares()[0].dragging.on, true);
});

test("stop disables dragging and drops the temporary square of a positionless battle", () => {
  const { layer, squares } = setup();
  const kursk = battle();
  const atlantic = battle({ title: "Atlantic", lat: null, lng: null });
  layer.setBattles([kursk, atlantic]);
  layer.startEdit(atlantic, { onMove() {} }).stop();
  assert.deepEqual(squares().map((m) => m.options.battleTitle), ["Battle of Kursk"]);
  const edit = layer.startEdit(kursk, { onMove() {} });
  edit.stop();
  assert.equal(squares().length, 1);
  assert.equal(squares()[0].dragging.on, false);
});

test("starting a new edit stops the previous one", () => {
  const { layer, squares } = setup();
  const a = battle({ title: "a" });
  const b = battle({ title: "b", lat: 10, lng: 10 });
  layer.setBattles([a, b]);
  layer.startEdit(a, { onMove() {} });
  layer.startEdit(b, { onMove() {} });
  const enabled = Object.fromEntries(squares().map((m) => [m.options.battleTitle, m.dragging.on]));
  assert.deepEqual(enabled, { a: false, b: true });
});


test("a square carries the classes of its Winnaar, also when selected and own", () => {
  const { layer, squares } = setup();
  const won = battle({ winner: ["sovjet"] });
  const undecided = battle({ title: "draw", lat: 10, lng: 10, winner: ["as", "westers"], own: true });
  layer.setBattles([won, undecided, battle({ title: "unknown", lat: 20, lng: 20 })]);
  layer.setSelected(won);
  const classes = Object.fromEntries(squares().map((m) => [m.options.battleTitle, m.options.icon.className]));
  assert.equal(classes["Battle of Kursk"], "battle-square win1-sovjet selected");
  assert.equal(classes.draw, "battle-square win1-as win2-westers own");
  assert.equal(classes.unknown, "battle-square");
});

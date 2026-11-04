import { test } from "node:test";
import assert from "node:assert/strict";

import { turboColor } from "../js/color-ramp.js";
import {
  routeColor,
  statusLegStyle,
  rampValue,
  colorRange,
  patrolStart,
  patrolEnd,
  historyRange,
  inPeriod,
  newStatusState,
} from "../js/status-map.js";

const history = { min: "1940-01-01", max: "1945-01-01" };

test("routeColor is black only for the last crawled patrol", () => {
  assert.equal(routeColor({ external_id: "p1", departure_date: "1942-01-01" }, "p1", history), "#000000");
  assert.notEqual(routeColor({ external_id: "p2", departure_date: "1942-01-01" }, "p1", history), "#000000");
});

test("routeColor maps the oldest patrol to the lowest and the newest to the highest ramp value", () => {
  assert.equal(routeColor({ external_id: "old", departure_date: "1940-01-01" }, null, history), turboColor(0));
  assert.equal(routeColor({ external_id: "new", departure_date: "1945-01-01" }, null, history), turboColor(1));
});

test("routeColor is neutral for a patrol without any date", () => {
  assert.equal(routeColor({ external_id: "p", points: [] }, null, history), "#888888");
});

test("rampValue is zero when all patrols share one date", () => {
  assert.equal(rampValue("1940-01-01", { min: "1940-01-01", max: "1940-01-01" }), 0);
});

test("patrolStart and patrolEnd fall back on dated route points", () => {
  const patrol = { points: [{ date: null }, { date: "1941-02-01" }, { date: "1941-03-01" }] };
  assert.equal(patrolStart(patrol), "1941-02-01");
  assert.equal(patrolEnd(patrol), "1941-03-01");
  assert.equal(patrolEnd({ departure_date: "1941-02-01", points: [] }), "1941-02-01");
});

test("historyRange spans the oldest and newest departure, ignoring undated patrols", () => {
  assert.deepEqual(
    historyRange([
      { departure_date: "1943-01-01", points: [] },
      { departure_date: "1940-05-01", points: [] },
      { points: [] },
    ]),
    { min: "1940-05-01", max: "1943-01-01" },
  );
  assert.equal(historyRange([{ points: [] }]), null);
});

test("inPeriod keeps a patrol that overlaps the period, on the boundary days too", () => {
  const patrol = { departure_date: "1941-03-10", arrival_date: "1941-03-20", points: [] };
  assert.equal(inPeriod(patrol, null, null), true);
  assert.equal(inPeriod(patrol, "1941-03-20", null), true);
  assert.equal(inPeriod(patrol, "1941-03-21", null), false);
  assert.equal(inPeriod(patrol, null, "1941-03-10"), true);
  assert.equal(inPeriod(patrol, null, "1941-03-09"), false);
  assert.equal(inPeriod(patrol, "1941-03-15", "1941-03-16"), true);
});

test("inPeriod hides an undated patrol only when a period is set", () => {
  assert.equal(inPeriod({ points: [] }, null, null), true);
  assert.equal(inPeriod({ points: [] }, "1941-01-01", null), false);
});

test("inPeriod shows nothing when the start lies after the end", () => {
  const patrol = { departure_date: "1941-03-10", arrival_date: "1941-03-20", points: [] };
  assert.equal(inPeriod(patrol, "1941-03-20", "1941-03-10"), false);
});

test("statusLegStyle ignores suspect and keeps the page colour", () => {
  assert.deepEqual(statusLegStyle("ok", "#000000"), { color: "#000000", dashArray: "6 6" });
  assert.deepEqual(statusLegStyle("suspect", "#0077cc"), { color: "#0077cc", dashArray: "6 6" });
  for (const status of ["on_land", "no_route", "not_computed"]) {
    assert.equal(statusLegStyle(status, "#0077cc"), null);
  }
});

function fakeLeaflet() {
  const log = [];
  const makePolyline = (latLngs) => ({
    latLngs,
    style: null,
    setStyle(style) {
      this.style = style;
    },
    bindTooltip() {},
    addTo(group) {
      group.addLayer(this);
      return this;
    },
    bringToFront() {
      log.push(this.id);
    },
  });
  globalThis.L = {
    polyline: (latLngs) => makePolyline(latLngs),
    circleMarker: (latLng) => ({ ...makePolyline([latLng]), isMarker: true }),
  };
  return log;
}

test("updateRoutes keeps the last crawled patrol on top when another one is added", async () => {
  const log = fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const state = newState("red");
  const pts = [{ sequence: 0, lat: 1, lng: 1 }, { sequence: 1, lat: 2, lng: 2 }];
  const legs = [{ from_sequence: 0, to_sequence: 1, status: "ok", path: [[1, 1], [2, 2]] }];
  updateRoutes(state, [{ external_id: "red", boat_number: "U-1", points: pts, legs }]);
  state.polylines.get("red").id = "red";
  log.length = 0;

  updateRoutes(state, [{ external_id: "blue", boat_number: "U-2", points: pts, legs }]);

  assert.deepEqual(log, ["red"]);
});

function fakeLayer() {
  return {
    items: [],
    removeLayer(item) {
      this.items = this.items.filter((other) => other !== item);
    },
    hasLayer(item) {
      return this.items.includes(item);
    },
    addLayer(item) {
      this.items.push(item);
    },
  };
}

function newState(lastExternalId = null) {
  const state = newStatusState({ fitBounds() {} }, fakeLayer());
  state.fitted = true;
  state.lastExternalId = lastExternalId;
  return state;
}
const twoPoints = [{ sequence: 0, lat: 1, lng: 1 }, { sequence: 1, lat: 2, lng: 2 }];
const okLegs = [{ from_sequence: 0, to_sequence: 1, status: "ok", path: [[1, 1], [2, 2]] }];

test("setLastPatrol moves the black colour to the new patrol", async () => {
  fakeLeaflet();
  const { updateRoutes, setLastPatrol } = await import("../js/status-map.js");
  const state = newState("a");
  updateRoutes(state, [
    { external_id: "a", boat_number: "U-1", points: twoPoints, legs: okLegs },
    { external_id: "b", boat_number: "U-2", points: twoPoints, legs: okLegs },
  ]);
  assert.equal(state.polylines.get("a").style.color, "#000000");
  assert.equal(state.polylines.get("b").style.color, "#888888");

  setLastPatrol(state, "b");

  assert.equal(state.polylines.get("a").style.color, "#888888");
  assert.equal(state.polylines.get("b").style.color, "#000000");
});

test("a route arriving after setLastPatrol becomes black", async () => {
  fakeLeaflet();
  const { updateRoutes, setLastPatrol } = await import("../js/status-map.js");
  const state = newState();
  setLastPatrol(state, "late");

  updateRoutes(state, [{ external_id: "late", boat_number: "U-3", points: twoPoints, legs: okLegs }]);

  assert.equal(state.polylines.get("late").style.color, "#000000");
});

test("a one-point patrol is drawn as a marker coloured by the same rule", async () => {
  fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const state = newState("solo");

  updateRoutes(state, [
    { external_id: "solo", boat_number: "U-4", points: [{ lat: 1, lng: 1 }] },
    { external_id: "other", boat_number: "U-5", points: [{ lat: 2, lng: 2 }] },
    { external_id: "empty", boat_number: "U-6", points: [] },
  ]);

  assert.equal(state.polylines.get("solo").isMarker, true);
  assert.equal(state.polylines.get("solo").style.color, "#000000");
  assert.equal(state.polylines.get("other").style.color, "#888888");
  assert.equal(state.polylines.has("empty"), false);
});

test("a patrol draws one dashed multi-polyline from its drawable legs only", async () => {
  fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const state = newState();
  const points = [0, 1, 2, 3].map((i) => ({ sequence: i, lat: i, lng: i }));
  const legs = [
    { from_sequence: 0, to_sequence: 1, status: "ok", path: [[0, 0], [1, 1]] },
    { from_sequence: 1, to_sequence: 2, status: "on_land", path: null },
    { from_sequence: 2, to_sequence: 3, status: "suspect", path: [[2, 2], [3, 3]] },
  ];

  updateRoutes(state, [{ external_id: "a", boat_number: "U-1", points, legs }]);

  const line = state.polylines.get("a");
  assert.deepEqual(line.latLngs, [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]);
  assert.equal(line.style.dashArray, "6 6");
  assert.equal(line.style.color, "#888888");
});

test("a patrol without a drawable leg draws nothing and does not break fitting or recolouring", async () => {
  fakeLeaflet();
  const { updateRoutes, setLastPatrol } = await import("../js/status-map.js");
  const fits = [];
  const state = newState("a");
  state.fitted = false;
  state.map = { fitBounds: (...args) => fits.push(args) };
  const legs = [{ from_sequence: 0, to_sequence: 1, status: "not_computed", path: null }];

  updateRoutes(state, [{ external_id: "a", boat_number: "U-1", points: twoPoints, legs }]);
  setLastPatrol(state, "a");

  assert.equal(state.polylines.has("a"), false);
  assert.equal(fits.length, 1);
});

test("fitting uses route point coordinates, even with no computed routes", async () => {
  fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const fits = [];
  const state = newState();
  state.fitted = false;
  state.map = { fitBounds: (...args) => fits.push(args) };
  const legs = [{ from_sequence: 0, to_sequence: 1, status: "not_computed", path: null }];

  updateRoutes(state, [{ external_id: "a", boat_number: "U-1", points: twoPoints, legs }]);

  assert.deepEqual(fits[0][0], [[1, 1], [2, 2]]);
});

const dated = (id, departure, arrival) => ({
  external_id: id,
  boat_number: "U-1",
  departure_date: departure,
  arrival_date: arrival,
  points: twoPoints,
  legs: okLegs,
});

test("colorRange is the whole history without a period", () => {
  assert.deepEqual(colorRange(history, null, null), history);
});

test("colorRange follows the selected period, open ends falling back on history", () => {
  assert.deepEqual(colorRange(history, "1941-01-01", "1942-01-01"), { min: "1941-01-01", max: "1942-01-01" });
  assert.deepEqual(colorRange(history, "1941-01-01", null), { min: "1941-01-01", max: "1945-01-01" });
  assert.deepEqual(colorRange(history, null, "1942-01-01"), { min: "1940-01-01", max: "1942-01-01" });
});

test("colorRange is null without any history", () => {
  assert.equal(colorRange(null, null, null), null);
});

test("a selected period spans the whole ramp", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod } = await import("../js/status-map.js");
  const state = newState();
  updateRoutes(state, [
    dated("first", "1940-01-01", "1940-02-01"),
    dated("mid", "1941-07-02", "1941-08-01"),
    dated("end", "1942-01-01", "1942-02-01"),
    dated("late", "1945-01-01", "1945-02-01"),
  ]);

  setPeriod(state, "1940-01-01", "1942-01-01");

  assert.equal(state.polylines.get("first").style.color, turboColor(0));
  assert.equal(state.polylines.get("end").style.color, turboColor(1));
  assert.equal(
    state.polylines.get("mid").style.color,
    turboColor(rampValue("1941-07-02", { min: "1940-01-01", max: "1942-01-01" })),
  );
});

test("a patrol that departed before the period gets the lowest ramp colour", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod } = await import("../js/status-map.js");
  const state = newState();
  updateRoutes(state, [dated("a", "1940-12-20", "1941-01-20"), dated("b", "1945-01-01", "1945-02-01")]);

  setPeriod(state, "1941-01-01", "1942-01-01");

  assert.equal(state.polylines.get("a").style.color, turboColor(0));
});

test("clearing the period restores the colours over the whole history", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod } = await import("../js/status-map.js");
  const state = newState();
  updateRoutes(state, [dated("a", "1940-01-01", "1940-02-01"), dated("b", "1942-01-01", "1942-02-01")]);
  const before = state.polylines.get("b").style.color;

  setPeriod(state, "1941-12-01", "1942-01-01");
  setPeriod(state, null, null);

  assert.equal(state.polylines.get("b").style.color, before);
  assert.equal(before, turboColor(1));
});

test("a patrol arriving during a period is coloured by that period", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod } = await import("../js/status-map.js");
  const state = newState();
  updateRoutes(state, [dated("a", "1940-01-01", "1940-02-01"), dated("z", "1945-01-01", "1945-02-01")]);
  setPeriod(state, "1941-01-01", "1942-01-01");

  updateRoutes(state, [dated("new", "1942-01-01", "1942-02-01")]);

  assert.equal(state.polylines.get("new").style.color, turboColor(1));
});

test("the last crawled patrol stays black inside a period", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod } = await import("../js/status-map.js");
  const state = newState("a");
  updateRoutes(state, [dated("a", "1941-06-01", "1941-07-01"), dated("b", "1945-01-01", "1945-02-01")]);

  setPeriod(state, "1941-01-01", "1942-01-01");

  assert.equal(state.polylines.get("a").style.color, "#000000");
});

test("lines are drawn very thin", async () => {
  fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const state = newState("a");
  updateRoutes(state, [dated("a", "1940-01-01", "1940-02-01"), dated("b", "1941-01-01", "1941-02-01")]);
  assert.ok(state.polylines.get("a").style.weight < 1);
  assert.ok(state.polylines.get("b").style.weight < 1);
});

test("a new patrol extending history recolours the patrols already drawn", async () => {
  fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const state = newState();
  updateRoutes(state, [dated("a", "1940-01-01", "1940-02-01"), dated("b", "1941-01-01", "1941-02-01")]);
  assert.equal(state.polylines.get("b").style.color, turboColor(1));

  updateRoutes(state, [dated("c", "1942-01-01", "1942-02-01")]);

  assert.equal(
    state.polylines.get("b").style.color,
    turboColor(rampValue("1941-01-01", { min: "1940-01-01", max: "1942-01-01" })),
  );
  assert.equal(state.polylines.get("c").style.color, turboColor(1));
});

test("setPeriod hides lines outside the period and shows them again when cleared", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod, visibleCount } = await import("../js/status-map.js");
  const state = newState();
  updateRoutes(state, [dated("a", "1940-01-01", "1940-02-01"), dated("b", "1942-01-01", "1942-02-01")]);
  assert.deepEqual(visibleCount(state), { visible: 2, total: 2 });

  setPeriod(state, "1941-01-01", "1943-01-01");

  assert.equal(state.layer.hasLayer(state.polylines.get("a")), false);
  assert.equal(state.layer.hasLayer(state.polylines.get("b")), true);
  assert.deepEqual(visibleCount(state), { visible: 1, total: 2 });

  setPeriod(state, null, null);

  assert.equal(state.layer.hasLayer(state.polylines.get("a")), true);
});

test("a patrol arriving during a period stays hidden when it falls outside it", async () => {
  fakeLeaflet();
  const { updateRoutes, setPeriod, setLastPatrol } = await import("../js/status-map.js");
  const state = newState();
  setPeriod(state, "1941-01-01", "1943-01-01");

  setLastPatrol(state, "a");
  updateRoutes(state, [dated("a", "1940-01-01", "1940-02-01")]);

  assert.equal(state.layer.hasLayer(state.polylines.get("a")), false);
});

test("the last crawled patrol stays on top after a period change", async () => {
  const log = fakeLeaflet();
  const { updateRoutes, setPeriod } = await import("../js/status-map.js");
  const state = newState("a");
  updateRoutes(state, [dated("a", "1942-01-01", "1942-02-01"), dated("b", "1940-01-01", "1940-02-01")]);
  state.polylines.get("a").id = "a";
  setPeriod(state, "1941-01-01", null);
  log.length = 0;

  setPeriod(state, null, null);

  assert.deepEqual(log, ["a"]);
});

test("the tooltip names the boat, the patrol and its period", async () => {
  fakeLeaflet();
  const { routeTooltip } = await import("../js/status-map.js");
  assert.equal(
    routeTooltip(dated("patrol_1", "1940-01-01", "1940-02-01")),
    "U-1 — patrol_1 — 1940-01-01 t/m 1940-02-01",
  );
  assert.equal(routeTooltip({ boat_number: "U-1", external_id: "patrol_1", points: [] }), "U-1 — patrol_1");
});

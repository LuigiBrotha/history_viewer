import { test } from "node:test";
import assert from "node:assert/strict";

import { routeColor, statusLegStyle } from "../js/status-map.js";

test("routeColor is red only for the last crawled patrol", () => {
  assert.equal(routeColor({ external_id: "p1" }, "p1"), "#cc3300");
  assert.equal(routeColor({ external_id: "p2" }, "p1"), "#0077cc");
});

test("routeColor is blue for every patrol when nothing has been crawled yet", () => {
  assert.equal(routeColor({ external_id: "p1" }, null), "#0077cc");
});

test("statusLegStyle ignores suspect and keeps the page colour", () => {
  assert.deepEqual(statusLegStyle("ok", "#cc3300"), { color: "#cc3300", dashArray: "6 6" });
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
      group.items.push(this);
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

test("updateRoutes keeps the last crawled patrol on top when a blue one is added", async () => {
  const log = fakeLeaflet();
  const { updateRoutes } = await import("../js/status-map.js");
  const layer = { items: [], removeLayer() {}, getBounds: () => null };
  const state = {
    map: { fitBounds() {} },
    layer,
    polylines: new Map(),
    markers: new Set(),
    extents: new Map(),
    fitted: true,
    lastExternalId: "red",
  };
  const pts = [{ sequence: 0, lat: 1, lng: 1 }, { sequence: 1, lat: 2, lng: 2 }];
  const legs = [{ from_sequence: 0, to_sequence: 1, status: "ok", path: [[1, 1], [2, 2]] }];
  updateRoutes(state, [{ external_id: "red", boat_number: "U-1", points: pts, legs }]);
  state.polylines.get("red").id = "red";
  log.length = 0;

  updateRoutes(state, [{ external_id: "blue", boat_number: "U-2", points: pts, legs }]);

  assert.deepEqual(log, ["red"]);
});

function newState(lastExternalId = null) {
  return {
    map: { fitBounds() {} },
    layer: { items: [], removeLayer() {}, getBounds: () => null },
    polylines: new Map(),
    markers: new Set(),
    extents: new Map(),
    fitted: true,
    lastExternalId,
  };
}
const twoPoints = [{ sequence: 0, lat: 1, lng: 1 }, { sequence: 1, lat: 2, lng: 2 }];
const okLegs = [{ from_sequence: 0, to_sequence: 1, status: "ok", path: [[1, 1], [2, 2]] }];

test("setLastPatrol moves the red colour to the new patrol", async () => {
  fakeLeaflet();
  const { updateRoutes, setLastPatrol } = await import("../js/status-map.js");
  const state = newState("a");
  updateRoutes(state, [
    { external_id: "a", boat_number: "U-1", points: twoPoints, legs: okLegs },
    { external_id: "b", boat_number: "U-2", points: twoPoints, legs: okLegs },
  ]);
  assert.equal(state.polylines.get("a").style.color, "#cc3300");
  assert.equal(state.polylines.get("b").style.color, "#0077cc");

  setLastPatrol(state, "b");

  assert.equal(state.polylines.get("a").style.color, "#0077cc");
  assert.equal(state.polylines.get("b").style.color, "#cc3300");
});

test("a route arriving after setLastPatrol becomes red", async () => {
  fakeLeaflet();
  const { updateRoutes, setLastPatrol } = await import("../js/status-map.js");
  const state = newState();
  setLastPatrol(state, "late");

  updateRoutes(state, [{ external_id: "late", boat_number: "U-3", points: twoPoints, legs: okLegs }]);

  assert.equal(state.polylines.get("late").style.color, "#cc3300");
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
  assert.equal(state.polylines.get("solo").style.color, "#cc3300");
  assert.equal(state.polylines.get("other").style.color, "#0077cc");
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
  assert.equal(line.style.color, "#0077cc");
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

import { test } from "node:test";
import assert from "node:assert/strict";

import { routeColor, routeLatLngs } from "../js/status-map.js";

test("routeColor is red only for the last crawled patrol", () => {
  assert.equal(routeColor({ external_id: "p1" }, "p1"), "#cc3300");
  assert.equal(routeColor({ external_id: "p2" }, "p1"), "#0077cc");
});

test("routeColor is blue for every patrol when nothing has been crawled yet", () => {
  assert.equal(routeColor({ external_id: "p1" }, null), "#0077cc");
});

test("routeLatLngs maps points to [lat, lng] pairs", () => {
  const patrol = { points: [{ lat: 1, lng: 2 }, { lat: 3, lng: 4 }] };
  assert.deepEqual(routeLatLngs(patrol), [[1, 2], [3, 4]]);
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
    fitted: true,
    lastExternalId: "red",
  };
  const pts = [{ lat: 1, lng: 1 }, { lat: 2, lng: 2 }];
  updateRoutes(state, [{ external_id: "red", boat_number: "U-1", points: pts }]);
  state.polylines.get("red").id = "red";
  log.length = 0;

  updateRoutes(state, [{ external_id: "blue", boat_number: "U-2", points: pts }]);

  assert.deepEqual(log, ["red"]);
});

function newState(lastExternalId = null) {
  return {
    map: { fitBounds() {} },
    layer: { items: [], removeLayer() {}, getBounds: () => null },
    polylines: new Map(),
    fitted: true,
    lastExternalId,
  };
}
const twoPoints = [{ lat: 1, lng: 1 }, { lat: 2, lng: 2 }];

test("setLastPatrol moves the red colour to the new patrol", async () => {
  fakeLeaflet();
  const { updateRoutes, setLastPatrol } = await import("../js/status-map.js");
  const state = newState("a");
  updateRoutes(state, [
    { external_id: "a", boat_number: "U-1", points: twoPoints },
    { external_id: "b", boat_number: "U-2", points: twoPoints },
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

  updateRoutes(state, [{ external_id: "late", boat_number: "U-3", points: twoPoints }]);

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

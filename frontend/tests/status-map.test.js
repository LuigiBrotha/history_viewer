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
    setStyle() {},
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

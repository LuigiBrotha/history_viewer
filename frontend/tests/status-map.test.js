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

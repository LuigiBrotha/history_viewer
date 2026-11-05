import { test } from "node:test";
import assert from "node:assert/strict";

import { createPacificToggle, isPacificShown, PACIFIC_BOUNDS } from "../js/pacific-view.js";

function fakeMap() {
  const calls = [];
  return {
    calls,
    getCenter: () => ({ lat: 54.5, lng: 8 }),
    getZoom: () => 5,
    fitBounds: (bounds) => calls.push(["fit", bounds]),
    setView: (center, zoom) => calls.push(["view", center, zoom]),
  };
}

test("the Pacific view has Asia on the left and America on the right, across the date line", () => {
  const [[, west], [, east]] = PACIFIC_BOUNDS;
  assert.ok(west < 180 && east > 180);
  assert.ok(west <= 100, "Asia in view");
  assert.ok(east >= 240, "the American west coast in view");
});

test("toggling goes to the Pacific and back to where the map was", () => {
  const map = fakeMap();
  const toggle = createPacificToggle(map);
  assert.equal(toggle(), true);
  assert.deepEqual(map.calls[0], ["fit", PACIFIC_BOUNDS]);
  assert.equal(toggle(), false);
  assert.deepEqual(map.calls[1], ["view", { lat: 54.5, lng: 8 }, 5]);
});

test("isPacificShown lets the first fit after loading leave a chosen Pacific view alone", () => {
  const map = fakeMap();
  const toggle = createPacificToggle(map);
  assert.equal(isPacificShown(map), false);
  toggle();
  assert.equal(isPacificShown(map), true);
  toggle();
  assert.equal(isPacificShown(map), false);
});

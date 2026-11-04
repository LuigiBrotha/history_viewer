import { test } from "node:test";
import assert from "node:assert/strict";

import { renderFollowedRoute } from "../js/map.js";

function setup() {
  const fits = [];
  globalThis.L = {
    polyline: () => ({ addTo() { return this; }, getBounds: () => "bounds" }),
    circleMarker: () => ({ addTo() { return this; } }),
  };
  const mapState = {
    map: { fitBounds: (...args) => fits.push(args) },
    followedRouteLayer: { clearLayers() {} },
    fittedExternalId: null,
  };
  return { mapState, fits };
}

const patrol = (external_id) => ({ external_id, points: [{ lat: 1, lng: 1 }, { lat: 2, lng: 2 }] });

test("renderFollowedRoute fits a new patrol on a user action", () => {
  const { mapState, fits } = setup();
  renderFollowedRoute(mapState, patrol("p1"), null, { fit: true });
  assert.equal(fits.length, 1);
  assert.equal(mapState.fittedExternalId, "p1");
});

test("a live update with a new patrol keeps the user's view but records it as fitted", () => {
  const { mapState, fits } = setup();
  renderFollowedRoute(mapState, patrol("p1"), null, { fit: true });
  fits.length = 0;

  renderFollowedRoute(mapState, patrol("p2"), null, { fit: false });
  assert.equal(fits.length, 0);
  assert.equal(mapState.fittedExternalId, "p2");

  // The next slider step on the same patrol must not jump either.
  renderFollowedRoute(mapState, patrol("p2"), null, { fit: true });
  assert.equal(fits.length, 0);
});

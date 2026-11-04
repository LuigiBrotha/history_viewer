import { test } from "node:test";
import assert from "node:assert/strict";

import { renderActiveBoats, renderFollowedRoute } from "../js/map.js";

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

function recordingLeaflet() {
  const made = [];
  const make = (kind) => (...args) => {
    const item = { kind, args, tooltip: null };
    item.addTo = () => item;
    item.bindTooltip = (text) => {
      item.tooltip = text;
      return item;
    };
    item.on = () => item;
    item.getBounds = () => "bounds";
    made.push(item);
    return item;
  };
  globalThis.L = {
    polyline: make("polyline"),
    circleMarker: make("circleMarker"),
    marker: make("marker"),
    divIcon: (options) => options,
  };
  return made;
}

const legPatrol = {
  external_id: "p1",
  points: [
    { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
    { sequence: 1, lat: 2, lng: 2, date: "2020-01-02" },
    { sequence: 2, lat: 4, lng: 6, date: "2020-01-03" },
    { sequence: 3, lat: 5, lng: 7, date: "2020-01-04" },
  ],
  legs: [
    { from_sequence: 0, to_sequence: 1, status: "ok", reason: null, path: [[0, 0], [1, 1], [2, 2]] },
    { from_sequence: 1, to_sequence: 2, status: "suspect", reason: "te ver", path: [[2, 2], [4, 6]] },
    { from_sequence: 2, to_sequence: 3, status: "on_land", reason: "over land", path: null },
  ],
};

test("a followed route draws dashed legs, dots, and a ? label for uncertain legs", () => {
  const made = recordingLeaflet();
  const fits = [];
  const state = {
    map: { fitBounds: (...a) => fits.push(a) },
    followedRouteLayer: { clearLayers() {} },
    fittedExternalId: null,
  };
  renderFollowedRoute(state, legPatrol, { lat: 5, lng: 7, sequence: 3 }, { fit: true });

  const lines = made.filter((m) => m.kind === "polyline");
  assert.equal(lines.length, 2);
  assert.equal(lines[0].args[1].dashArray, "6 6");
  assert.equal(lines[1].args[1].color, "#e67e00");
  assert.equal(lines[1].tooltip, "te ver");
  assert.equal(made.filter((m) => m.kind === "circleMarker" && m.args[1].radius === 3).length, 4);
  const labels = made.filter((m) => m.kind === "marker");
  assert.equal(labels.length, 1);
  assert.deepEqual(labels[0].args[0], [4.5, 6.5]);
  assert.equal(labels[0].args[1].icon.className, "leg-uncertain");
  assert.equal(labels[0].tooltip, "over land");
  assert.equal(fits.length, 1);
  assert.equal(fits[0][0].length, 4 + 3 + 2);
});

test("a followed route with no computed legs and one point still fits", () => {
  recordingLeaflet();
  const fits = [];
  const state = {
    map: { fitBounds: (...a) => fits.push(a) },
    followedRouteLayer: { clearLayers() {} },
    fittedExternalId: null,
  };
  const patrol = {
    external_id: "p",
    points: [{ sequence: 0, lat: 1, lng: 1 }],
    legs: [],
  };
  renderFollowedRoute(state, patrol, null, { fit: true });
  assert.deepEqual(fits[0][0], [[1, 1]]);
});

test("the overview draws only the tail leg and flags an uncertain one", () => {
  const made = recordingLeaflet();
  const state = { activeBoatsLayer: { clearLayers() {} } };
  const boat = (sequence) => ({
    boatSlug: "u1", boatNumber: "U-1", lat: 1, lng: 1, positionDate: "2020-01-02", sequence, patrol: legPatrol,
  });
  renderActiveBoats(state, [boat(1)], () => {});
  assert.equal(made.filter((m) => m.kind === "polyline").length, 1);
  assert.equal(made.find((m) => m.kind === "circleMarker").tooltip, "U-1 — positie van 2020-01-02");

  made.length = 0;
  renderActiveBoats(state, [boat(3)], () => {});
  assert.equal(made.filter((m) => m.kind === "polyline").length, 0);
  assert.match(made.find((m) => m.kind === "circleMarker").tooltip, / — route onzeker$/);
});

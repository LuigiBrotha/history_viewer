import { test } from "node:test";
import assert from "node:assert/strict";

import {
  beginEdit,
  clearEditError,
  createEditState,
  failEdit,
  finishEdit,
  followStatusText,
  followedRouteChanged,
  isBusy,
  reopenPoint,
} from "../js/edit-state.js";

const patrol = { external_id: "p1", points: [{ sequence: 1 }, { sequence: 3 }] };
const position = { lat: 1, lng: 2, date: "1940-06-18", sequence: 1, dateApproximate: false };

test("a poll that changes nothing about the followed boat does not redraw its route", () => {
  const before = { patrol, position, editable: true };
  assert.equal(followedRouteChanged(before, { patrol, position: { ...position }, editable: true }), false);
});

test("a changed patrol object, position or edit permission redraws the route", () => {
  const before = { patrol, position, editable: true };
  assert.equal(followedRouteChanged(before, { patrol: { ...patrol }, position, editable: true }), true);
  assert.equal(followedRouteChanged(before, { patrol, position: { ...position, lat: 9 }, editable: true }), true);
  assert.equal(followedRouteChanged(before, { patrol, position: null, editable: true }), true);
  assert.equal(followedRouteChanged(before, { patrol, position, editable: false }), true);
});

test("the first draw, and a draw after the route was cleared, always happens", () => {
  assert.equal(followedRouteChanged(null, { patrol, position, editable: true }), true);
  assert.equal(followedRouteChanged(null, { patrol: null, position: null, editable: false }), true);
});

const openAt = (externalId, sequence, lat, lng) => ({ externalId, sequence, lat, lng });
const routeWith = (externalId, ...points) => ({ external_id: externalId, points });

test("reopenPoint keeps the popup on the same point of the same patrol", () => {
  const p = routeWith("p1", { sequence: 1, lat: 1, lng: 1 }, { sequence: 3, lat: 3, lng: 4 });
  const open = openAt("p1", 3, 3, 4);
  assert.equal(reopenPoint(open, p), open);
  assert.equal(reopenPoint(openAt("p1", 2, 3, 4), p), null);
  assert.equal(reopenPoint(null, p), null);
  assert.equal(reopenPoint(undefined, p), null);
  assert.equal(reopenPoint(open, null), null);
});

test("reopenPoint ignores another patrol that has the same sequence", () => {
  const other = routeWith("p2", { sequence: 3, lat: 3, lng: 4 });
  assert.equal(reopenPoint(openAt("p1", 3, 3, 4), other), null);
});

test("reopenPoint ignores a point whose coordinates changed", () => {
  const p = routeWith("p1", { sequence: 3, lat: 9, lng: 9 });
  assert.equal(reopenPoint(openAt("p1", 3, 3, 4), p), null);
});

test("an in-flight point is busy until the edit finishes, and a second attempt is refused", () => {
  const state = createEditState();
  assert.equal(isBusy(state, "p1", 2), false);
  assert.equal(beginEdit(state, "p1", 2), true);
  assert.equal(isBusy(state, "p1", 2), true);
  assert.equal(isBusy(state, "p1", 3), false);
  assert.equal(isBusy(state, "p2", 2), false);
  assert.equal(beginEdit(state, "p1", 2), false);
  finishEdit(state, "p1", 2);
  assert.equal(isBusy(state, "p1", 2), false);
  assert.equal(beginEdit(state, "p1", 2), true);
});

test("a failed edit keeps its message until the next attempt, a boat selection or a reset", () => {
  const state = createEditState();
  beginEdit(state, "p1", 2);
  failEdit(state, "p1", 2, "Uitsluiten mislukt");
  assert.equal(isBusy(state, "p1", 2), false);
  assert.equal(state.error, "Uitsluiten mislukt");
  beginEdit(state, "p1", 2);
  assert.equal(state.error, "");
  failEdit(state, "p1", 2, "Herstellen mislukt");
  clearEditError(state);
  assert.equal(state.error, "");
});

test("a refused second attempt leaves an earlier error alone", () => {
  const state = createEditState();
  beginEdit(state, "p1", 2);
  beginEdit(state, "p1", 3);
  failEdit(state, "p1", 3, "boom");
  assert.equal(beginEdit(state, "p1", 2), false);
  assert.equal(state.error, "boom");
});

test("followStatusText shows the not-on-patrol message and the edit error together", () => {
  assert.equal(followStatusText("", ""), "");
  assert.equal(followStatusText("U-99 is niet op patrouille.", ""), "U-99 is niet op patrouille.");
  assert.equal(followStatusText("", "Uitsluiten mislukt"), "Uitsluiten mislukt");
  assert.equal(
    followStatusText("U-99 is niet op patrouille.", "Uitsluiten mislukt"),
    "U-99 is niet op patrouille. · Uitsluiten mislukt",
  );
});

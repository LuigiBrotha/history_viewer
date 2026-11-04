import { test } from "node:test";
import assert from "node:assert/strict";

import { activeBoatsOnDate, parseDate } from "../js/time-model.js";
import { boatColor } from "../js/boat-color.js";
import { pointPopup, renderActiveBoats, renderFollowedRoute } from "../js/map.js";
import { installFakeDom } from "./fake-dom.js";

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

test("activeBoatsOnDate feeds renderActiveBoats so the tail leg and the uncertain note show", () => {
  const made = recordingLeaflet();
  const state = { activeBoatsLayer: { clearLayers() {} } };
  const routes = [{ ...legPatrol, boat_slug: "u1", boat_number: "U-1" }];

  renderActiveBoats(state, activeBoatsOnDate(routes, parseDate("2020-01-02")), () => {});
  assert.equal(made.filter((m) => m.kind === "polyline").length, 1);

  made.length = 0;
  renderActiveBoats(state, activeBoatsOnDate(routes, parseDate("2020-01-04")), () => {});
  assert.match(made.find((m) => m.kind === "circleMarker").tooltip, / — route onzeker$/);
});

test("a boat at an approximated date gets a hollow marker", () => {
  const options = [];
  globalThis.L = {
    polyline: () => ({ addTo() { return this; } }),
    circleMarker: (_, markerOptions) => {
      options.push(markerOptions);
      return { bindTooltip() {}, on() {}, addTo() { return this; } };
    },
  };
  const state = { activeBoatsLayer: { clearLayers() {} } };
  const approximated = (approximate) => ({
    boat_slug: "u1",
    boat_number: "U-1",
    external_id: "p",
    points: [{ sequence: 0, lat: 1, lng: 1, date: "1940-01-01", date_approximate: approximate }],
    legs: [],
  });

  renderActiveBoats(state, activeBoatsOnDate([approximated(true)], parseDate("1940-01-01")), () => {});
  renderActiveBoats(state, activeBoatsOnDate([approximated(false)], parseDate("1940-01-01")), () => {});

  assert.ok(options[0].fillOpacity < options[1].fillOpacity);
});

test("a followed boat at an approximated date says so in its tooltip", () => {
  const tooltips = [];
  globalThis.L = {
    polyline: () => ({ addTo() { return this; } }),
    circleMarker: () => ({
      bindTooltip(text) {
        tooltips.push(text);
        return this;
      },
      addTo() {
        return this;
      },
    }),
  };
  const state = {
    map: { fitBounds() {} },
    followedRouteLayer: { clearLayers() {} },
    fittedExternalId: "p1",
  };

  renderFollowedRoute(
    state,
    { ...patrol("p1"), boat_number: "U-1" },
    { lat: 1, lng: 1, date: "1940-01-01", dateApproximate: true },
    { fit: false },
  );

  assert.deepEqual(tooltips, ["U-1 — positie van 1940-01-01 (datum benaderd)"]);
});

test("a boat's marker and tail take the boat's own colour; a suspect tail stays orange", () => {
  const markers = [];
  const lines = [];
  globalThis.L = {
    polyline: (_, options) => {
      lines.push(options);
      return { addTo() { return this; } };
    },
    circleMarker: (_, options) => {
      markers.push(options);
      return { bindTooltip() {}, on() {}, addTo() { return this; } };
    },
  };
  const state = { activeBoatsLayer: { clearLayers() {} } };
  const route = (status) => ({
    boat_slug: "u99",
    boat_number: "U-99",
    external_id: "p",
    points: [
      { sequence: 0, lat: 1, lng: 1, date: "1940-01-01" },
      { sequence: 1, lat: 2, lng: 2, date: "1940-01-02" },
    ],
    legs: [{ from_sequence: 0, to_sequence: 1, status, path: [[1, 1], [2, 2]] }],
  });

  renderActiveBoats(state, activeBoatsOnDate([route("ok")], parseDate("1940-01-02")), () => {});
  renderActiveBoats(state, activeBoatsOnDate([route("suspect")], parseDate("1940-01-02")), () => {});

  assert.equal(markers[0].fillColor, boatColor("u99"));
  assert.equal(lines[0].color, boatColor("u99"));
  assert.equal(lines[1].color, "#e67e00");
});

test("a followed route takes the boat's own colour", () => {
  const lines = [];
  const dots = [];
  globalThis.L = {
    polyline: (_, options) => {
      lines.push(options);
      return { addTo() { return this; }, bindTooltip() {} };
    },
    circleMarker: (_, options) => {
      dots.push(options);
      return { addTo() { return this; }, bindTooltip() { return this; } };
    },
  };
  const state = { map: { fitBounds() {} }, followedRouteLayer: { clearLayers() {} }, fittedExternalId: "p" };
  const followed = {
    external_id: "p",
    boat_slug: "u99",
    boat_number: "U-99",
    points: [{ sequence: 0, lat: 1, lng: 1 }, { sequence: 1, lat: 2, lng: 2 }],
    legs: [{ from_sequence: 0, to_sequence: 1, status: "ok", path: [[1, 1], [2, 2]] }],
  };

  renderFollowedRoute(state, followed, { lat: 1, lng: 1, date: "1940-01-01" }, { fit: false });

  assert.equal(lines[0].color, boatColor("u99"));
  assert.equal(dots[0].color, boatColor("u99"));
  assert.equal(dots.at(-1).fillColor, boatColor("u99"));
});

test("pointPopup shows the date, and marks an approximate one", () => {
  const root = installFakeDom();
  const exact = pointPopup({ sequence: 1, date: "1940-06-18" }, { onExclude: null, busy: false });
  const approx = pointPopup({ sequence: 1, date: "1940-06-18", date_approximate: true }, { onExclude: null, busy: false });
  const none = pointPopup({ sequence: 1, date: null }, { onExclude: null, busy: false });
  assert.equal(exact.children[0].textContent, "1940-06-18");
  assert.equal(approx.children[0].textContent, "1940-06-18 (datum benaderd)");
  assert.equal(none.children[0].textContent, "geen datum");
  assert.equal(root.find("button").length, 0);
  assert.equal(exact.find("button").length, 0);
});

test("pointPopup offers Punt uitsluiten only when editing is allowed", () => {
  installFakeDom();
  const calls = [];
  const box = pointPopup({ sequence: 2, date: null }, { onExclude: (point, button) => calls.push([point.sequence, button]), busy: false });
  const [button] = box.find("button");
  assert.equal(button.textContent, "Punt uitsluiten");
  assert.equal(button.disabled, false);
  button.click();
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 2);
  assert.equal(calls[0][1], button);
});

test("pointPopup for a point in flight shows a disabled Bezig… button", () => {
  installFakeDom();
  let clicks = 0;
  const box = pointPopup({ sequence: 2, date: null }, { onExclude: () => clicks++, busy: true });
  const [button] = box.find("button");
  assert.equal(button.textContent, "Bezig…");
  assert.equal(button.disabled, true);
  button.click();
  assert.equal(clicks, 0);
});

function popupLeaflet() {
  installFakeDom();
  const markers = [];
  globalThis.L = {
    polyline: () => ({ addTo() { return this; } }),
    circleMarker: ([lat, lng], options) => {
      const marker = {
        lat,
        lng,
        options,
        popups: [],
        opened: 0,
        handlers: {},
        addTo() { return this; },
        bindTooltip() { return this; },
        bindPopup(content, popupOptions) { this.popups.push({ content, popupOptions }); return this; },
        on(type, handler) { this.handlers[type] = handler; return this; },
        openPopup() { this.opened += 1; },
      };
      markers.push(marker);
      return marker;
    },
  };
  const mapState = {
    map: { fitBounds() {} },
    followedRouteLayer: { clearLayers() {} },
    fittedExternalId: null,
  };
  return { markers, mapState };
}

const route = (externalId, ...points) => ({ external_id: externalId, boat_number: "U-1", points });

test("renderFollowedRoute reopens the popup of the point that was open without panning the map", () => {
  const { markers, mapState } = popupLeaflet();
  mapState.openPoint = { externalId: "p1", sequence: 3, lat: 3, lng: 3 };
  const p = route("p1", { sequence: 1, lat: 1, lng: 1 }, { sequence: 3, lat: 3, lng: 3 });

  renderFollowedRoute(mapState, p, null, { fit: false });

  assert.deepEqual(markers.map((m) => m.opened), [0, 1]);
  assert.equal(markers[1].popups[0].popupOptions.autoPan, false);
  assert.equal(markers[0].popups[0].popupOptions.autoPan, true);
});

test("a popup is not reopened for a vanished point", () => {
  const { markers, mapState } = popupLeaflet();
  mapState.openPoint = { externalId: "p1", sequence: 2, lat: 2, lng: 2 };
  const p = route("p1", { sequence: 1, lat: 1, lng: 1 }, { sequence: 3, lat: 3, lng: 3 });

  renderFollowedRoute(mapState, p, null, { fit: false });

  assert.deepEqual(markers.map((m) => m.opened), [0, 0]);
  assert.equal(mapState.openPoint, null, "a later redraw does not reopen it either");
});

test("dragging into another patrol with the same sequence does not reopen a popup", () => {
  const { markers, mapState } = popupLeaflet();
  const first = route("p1", { sequence: 1, lat: 1, lng: 1 }, { sequence: 2, lat: 2, lng: 2 });
  const second = route("p2", { sequence: 1, lat: 1, lng: 1 }, { sequence: 2, lat: 2, lng: 2 });
  renderFollowedRoute(mapState, first, null, { fit: false });
  markers[1].handlers.popupopen();
  assert.deepEqual(mapState.openPoint, { externalId: "p1", sequence: 2, lat: 2, lng: 2 });
  markers.length = 0;

  renderFollowedRoute(mapState, second, null, { fit: false });

  assert.deepEqual(markers.map((m) => m.opened), [0, 0]);
});

test("the current-position marker carries the popup of its point and reopens it", () => {
  const { markers, mapState } = popupLeaflet();
  mapState.openPoint = { externalId: "p1", sequence: 2, lat: 2, lng: 2 };
  const p = route(
    "p1",
    { sequence: 1, lat: 1, lng: 1, date: "1940-06-18" },
    { sequence: 2, lat: 2, lng: 2, date: "1940-06-19", date_approximate: true },
  );
  const position = { lat: 2, lng: 2, date: "1940-06-19", sequence: 2, dateApproximate: true };
  const clicks = [];

  renderFollowedRoute(mapState, p, position, { fit: false, onExclude: (point) => clicks.push(point.sequence) });

  const marker = markers[markers.length - 1];
  assert.equal(marker.options.radius, 8);
  assert.equal(marker.popups.length, 1);
  const box = marker.popups[0].content();
  assert.equal(box.children[0].textContent, "1940-06-19 (datum benaderd)");
  box.children[1].click();
  assert.deepEqual(clicks, [2]);
  assert.deepEqual(markers.map((m) => m.opened), [0, 0, 1], "only the marker on top reopens it");
  marker.handlers.popupopen();
  assert.deepEqual(mapState.openPoint, { externalId: "p1", sequence: 2, lat: 2, lng: 2 });
});

test("a read-only current-position popup shows only the date", () => {
  const { markers, mapState } = popupLeaflet();
  const p = route("p1", { sequence: 1, lat: 1, lng: 1, date: "1940-06-18" });
  renderFollowedRoute(mapState, p, { lat: 1, lng: 1, date: "1940-06-18", sequence: 1, dateApproximate: false }, { fit: false });

  const box = markers[markers.length - 1].popups[0].content();
  assert.equal(box.children.length, 1);
  assert.equal(box.children[0].textContent, "1940-06-18");
});

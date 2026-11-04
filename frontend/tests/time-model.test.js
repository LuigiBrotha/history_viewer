import { test } from "node:test";
import assert from "node:assert/strict";

import {
  parseDate,
  datedPoints,
  knownPosition,
  lastLeg,
  activeBoatsOnDate,
  followView,
  positionLabel,
  notOnPatrolMessage,
  dateRange,
  shouldFitRoute,
} from "../js/time-model.js";

test("parseDate parses a YYYY-MM-DD string as UTC midnight", () => {
  const d = parseDate("1940-06-18");
  assert.equal(d.getUTCFullYear(), 1940);
  assert.equal(d.getUTCMonth(), 5);
  assert.equal(d.getUTCDate(), 18);
});

test("parseDate returns null for null, undefined, and empty input", () => {
  assert.equal(parseDate(null), null);
  assert.equal(parseDate(undefined), null);
  assert.equal(parseDate(""), null);
});

test("datedPoints filters out points with a null date, preserving order", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 1, lng: 1, date: "2020-01-01" },
      { sequence: 1, lat: 2, lng: 2, date: null },
      { sequence: 2, lat: 3, lng: 3, date: "2020-01-03" },
    ],
  };

  const dated = datedPoints(patrol);

  assert.equal(dated.length, 2);
  assert.deepEqual(dated.map((p) => p.sequence), [0, 2]);
});

const twoPointPatrol = {
  points: [
    { sequence: 0, lat: 54.0, lng: 10.0, date: "1940-06-18" },
    { sequence: 1, lat: 56.0, lng: 12.0, date: "1940-06-20" },
  ],
};

test("knownPosition returns the exact coordinate on a date with a route point", () => {
  assert.deepEqual(knownPosition(twoPointPatrol, parseDate("1940-06-20")), {
    lat: 56.0,
    lng: 12.0,
    date: "1940-06-20",
  });
});

test("knownPosition stays on the last known coordinate between two route points", () => {
  assert.deepEqual(knownPosition(twoPointPatrol, parseDate("1940-06-19")), {
    lat: 54.0,
    lng: 10.0,
    date: "1940-06-18",
  });
});

test("knownPosition uses the last route point when a date has several", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 1, lng: 1, date: "2020-01-01" },
      { sequence: 1, lat: 2, lng: 2, date: "2020-01-01" },
    ],
  };

  assert.deepEqual(knownPosition(patrol, parseDate("2020-01-01")), { lat: 2, lng: 2, date: "2020-01-01" });
});

test("knownPosition ignores an undated point sitting between two dated points", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
      { sequence: 1, lat: 99, lng: 99, date: null },
      { sequence: 2, lat: 4, lng: 8, date: "2020-01-03" },
    ],
  };

  assert.deepEqual(knownPosition(patrol, parseDate("2020-01-02")), { lat: 0, lng: 0, date: "2020-01-01" });
});

test("knownPosition returns null before the patrol's first dated point", () => {
  assert.equal(knownPosition(twoPointPatrol, parseDate("1940-06-17")), null);
});

test("knownPosition returns null after the patrol's last dated point", () => {
  assert.equal(knownPosition(twoPointPatrol, parseDate("1940-06-21")), null);
});

test("knownPosition returns null for a patrol with zero dated points", () => {
  const patrol = { points: [{ sequence: 0, lat: 1, lng: 1, date: null }] };

  assert.equal(knownPosition(patrol, parseDate("2020-01-01")), null);
});

test("lastLeg connects the two route points up to the given date", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 1, lng: 1, date: "2020-01-01" },
      { sequence: 1, lat: 2, lng: 2, date: "2020-01-02" },
      { sequence: 2, lat: 3, lng: 3, date: "2020-01-05" },
    ],
  };

  assert.deepEqual(lastLeg(patrol, parseDate("2020-01-03")), [
    [1, 1],
    [2, 2],
  ]);
});

test("lastLeg returns null on the patrol's first route point", () => {
  assert.equal(lastLeg(twoPointPatrol, parseDate("1940-06-18")), null);
});

const firstPatrol = {
  boat_number: "U-1",
  points: [
    { sequence: 0, lat: 1, lng: 1, date: "1940-01-01" },
    { sequence: 1, lat: 2, lng: 2, date: "1940-01-10" },
  ],
};
const secondPatrol = {
  boat_number: "U-1",
  points: [
    { sequence: 0, lat: 3, lng: 3, date: "1940-03-01" },
    { sequence: 1, lat: 4, lng: 4, date: "1940-03-10" },
  ],
};

test("followView shows the patrol active on the date, not the boat's first patrol", () => {
  const view = followView([firstPatrol, secondPatrol], parseDate("1940-03-01"));

  assert.equal(view.patrol, secondPatrol);
  assert.deepEqual(view.position, { lat: 3, lng: 3, date: "1940-03-01" });
});

test("followView does not depend on the order of the boat's patrols", () => {
  const view = followView([secondPatrol, firstPatrol], parseDate("1940-01-01"));

  assert.equal(view.patrol, firstPatrol);
});

test("followView keeps the last finished patrol without a position between patrols", () => {
  const view = followView([firstPatrol, secondPatrol], parseDate("1940-02-01"));

  assert.equal(view.patrol, firstPatrol);
  assert.equal(view.position, null);
});

test("followView has no patrol and no position before the boat's first patrol", () => {
  const view = followView([firstPatrol, secondPatrol], parseDate("1939-12-31"));

  assert.equal(view.patrol, null);
  assert.equal(view.position, null);
});

test("positionLabel names the boat and the date of its route point", () => {
  assert.equal(
    positionLabel({ boatNumber: "U-1", positionDate: "1940-01-01" }),
    "U-1 — positie van 1940-01-01",
  );
});

test("notOnPatrolMessage names the boat and the selected date", () => {
  assert.equal(
    notOnPatrolMessage("U-1", parseDate("1940-02-01")),
    "U-1 is op 1940-02-01 niet op patrouille.",
  );
});

test("activeBoatsOnDate includes only patrols active on the given date", () => {
  const routes = [
    {
      boat_slug: "u1",
      boat_number: "U-1",
      external_id: "patrol_1",
      points: [
        { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
        { sequence: 1, lat: 10, lng: 10, date: "2020-01-05" },
      ],
    },
    {
      boat_slug: "u2",
      boat_number: "U-2",
      external_id: "patrol_2",
      points: [
        { sequence: 0, lat: 20, lng: 20, date: "2020-02-01" },
        { sequence: 1, lat: 30, lng: 30, date: "2020-02-05" },
      ],
    },
  ];

  const active = activeBoatsOnDate(routes, parseDate("2020-01-03"));

  assert.equal(active.length, 1);
  assert.equal(active[0].boatSlug, "u1");
  assert.equal(active[0].boatNumber, "U-1");
  assert.equal(active[0].externalId, "patrol_1");
  assert.equal(active[0].lat, 0);
  assert.equal(active[0].positionDate, "2020-01-01");
  assert.equal(active[0].tail, null);
});

test("dateRange returns the min and max dated point across all routes, ignoring undated points", () => {
  const routes = [
    {
      points: [
        { sequence: 0, lat: 0, lng: 0, date: "2020-03-01" },
        { sequence: 1, lat: 1, lng: 1, date: null },
      ],
    },
    {
      points: [
        { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
        { sequence: 1, lat: 1, lng: 1, date: "2020-05-01" },
      ],
    },
  ];

  const range = dateRange(routes);

  assert.equal(range.min.getTime(), parseDate("2020-01-01").getTime());
  assert.equal(range.max.getTime(), parseDate("2020-05-01").getTime());
});

test("dateRange returns null when no route has any dated point", () => {
  const routes = [{ points: [{ sequence: 0, lat: 0, lng: 0, date: null }] }];

  assert.equal(dateRange(routes), null);
});

test("shouldFitRoute is false for a new object of the same patrol", () => {
  assert.equal(shouldFitRoute("patrol_1", { external_id: "patrol_1" }), false);
});

test("shouldFitRoute is true for another patrol", () => {
  assert.equal(shouldFitRoute("patrol_1", { external_id: "patrol_2" }), true);
  assert.equal(shouldFitRoute(null, { external_id: "patrol_2" }), true);
});

test("shouldFitRoute is false when there is no patrol", () => {
  assert.equal(shouldFitRoute(null, null), false);
});

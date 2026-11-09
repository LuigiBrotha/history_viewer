import { test } from "node:test";
import assert from "node:assert/strict";

import { boatSubjects, firstPatrolDate, hitByDate, hitInPeriod, shipSubjects } from "../js/subject-model.js";

test("boats are in number order and say type, patrols and tonnage", () => {
  const rows = boatSubjects([
    { slug: "u10", number: "U-10", type: "IIB", patrol_count: 1, tonnage: 0 },
    { slug: "u9", number: "U-9", type: "IIB", patrol_count: 2, tonnage: 12000 },
  ]);
  assert.deepEqual(rows.map((r) => r.title), ["U-9", "U-10"]);
  assert.equal(rows[0].meta, "IIB · 2 patrouilles · 12.000 ton");
  assert.equal(rows[1].meta, "IIB · 1 patrouille");
});

const hit = (over) => ({ ship_external_id: "1", name: "Magog", date: "1940-07-05", tons: 2053, outcome: "damaged", boat_slug: "u99", ...over });

test("a ship hit twice is one row, under its first date, with the last outcome", () => {
  const rows = shipSubjects([
    hit({ date: "1940-08-01", outcome: "sunk" }),
    hit({}),
    hit({ ship_external_id: "2", name: "Earlier", date: "1939-12-01", tons: 100, outcome: "sunk" }),
  ]);
  assert.deepEqual(rows.map((r) => r.title), ["Earlier", "Magog"]);
  assert.equal(rows[1].meta, "1940-07-05 · 2.053 ton · gezonken · 2 treffers");
  assert.deepEqual(rows[1].hits.map((h) => h.date), ["1940-07-05", "1940-08-01"]);
});

test("a ship counts from its first hit on, and for a period when any hit lies in it", () => {
  const ship = { hits: [hit({ date: "1940-07-05" }), hit({ date: "1940-08-01" })] };
  assert.equal(hitByDate(ship, "1940-07-04"), false);
  assert.equal(hitByDate(ship, "1940-07-05"), true);
  assert.equal(hitInPeriod(ship, "1940-07-10", "1940-07-20"), false);
  assert.equal(hitInPeriod(ship, "1940-07-10", null), true);
  assert.equal(hitInPeriod(ship, null, "1940-07-05"), true);
});

test("the first patrol date skips patrols without a date", () => {
  assert.equal(firstPatrolDate([{ departure_date: "1941-02-01", points: [] }, { departure_date: "1940-01-01", points: [] }, { departure_date: null, points: [] }]), "1940-01-01");
  assert.equal(firstPatrolDate([{ departure_date: null, points: [] }]), null);
});

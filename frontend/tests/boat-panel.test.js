import { test } from "node:test";
import assert from "node:assert/strict";

import { boatFacts, boatSummary, patrolLines, boatShips, shipLine } from "../js/boat-panel.js";

const boat = {
  slug: "u99",
  number: "U-99",
  type: "VIIB",
  builder: "Germaniawerft, Kiel",
  laid_down: "1939-03-31",
  launched: null,
  commissioned: "1940-04-18",
  fate: "Scuttled",
  patrols: [
    {
      external_id: "p1",
      patrol_number: 1,
      commander: "Otto Kretschmer",
      departure_port: "Kiel",
      departure_date: "1940-06-18",
      arrival_port: "Wilhelmshaven",
      arrival_date: "1940-06-25",
      days_at_sea: 8,
      tonnage: 12000,
    },
    { external_id: "p2", patrol_number: 2, tonnage: null },
  ],
};

test("boatFacts lists known facts in Dutch and skips unknown ones", () => {
  assert.deepEqual(boatFacts(boat), [
    ["Type", "VIIB"],
    ["Werf", "Germaniawerft, Kiel"],
    ["Kiel gelegd", "1939-03-31"],
    ["In dienst", "1940-04-18"],
    ["Lot", "Scuttled"],
  ]);
});

test("boatSummary counts patrols, tonnage and ships hit", () => {
  assert.equal(boatSummary(boat, [{}, {}]), "2 patrouilles · 12.000 ton · 2 getroffen schepen");
});

test("boatSummary uses the singular and leaves out unknowns", () => {
  assert.equal(boatSummary({ patrols: [{ tonnage: null }] }, []), "1 patrouille");
  assert.equal(boatSummary({ patrols: [] }, [{}]), "Geen patrouilles · 1 getroffen schip");
});

test("patrolLines describes a patrol in full", () => {
  assert.deepEqual(patrolLines(boat.patrols[0]), {
    title: "Patrouille 1",
    lines: [
      "Otto Kretschmer",
      "Kiel 1940-06-18 → Wilhelmshaven 1940-06-25",
      "8 dagen op zee · 12.000 ton",
    ],
  });
});

test("patrolLines leaves out what is unknown", () => {
  assert.deepEqual(patrolLines(boat.patrols[1]), { title: "Patrouille 2", lines: [] });
});

test("patrolLines handles one day and a missing port", () => {
  const { lines } = patrolLines({ patrol_number: 3, departure_date: "1940-01-01", arrival_port: "Kiel", days_at_sea: 1 });
  assert.deepEqual(lines, ["1940-01-01 → Kiel", "1 dag op zee"]);
});

test("boatShips picks this boat's ships, oldest first", () => {
  const ships = [
    { boat_slug: "u99", name: "B", date: "1940-08-01" },
    { boat_slug: "u47", name: "X", date: "1939-01-01" },
    { boat_slug: "u99", name: "A", date: "1940-07-01" },
  ];
  assert.deepEqual(boatShips(ships, "u99").map((ship) => ship.name), ["A", "B"]);
});

test("shipLine names date, ship, tonnage and outcome", () => {
  assert.equal(
    shipLine({ date: "1940-07-05", name: "Magog", tons: 2053, outcome: "sunk" }),
    "1940-07-05 · Magog · 2.053 ton · gezonken",
  );
});

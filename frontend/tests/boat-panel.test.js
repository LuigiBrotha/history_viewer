import { test } from "node:test";
import assert from "node:assert/strict";

import { boatFacts, boatSummary, patrolLines, boatShips, shipLine, shipFacts, hitLine, otherHits, hitBy, sourceUrl } from "../js/boat-panel.js";

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

const hit = {
  ship_external_id: "408",
  boat_slug: "u99",
  boat_number: "U-99",
  name: "Magog",
  date: "1940-07-05",
  tons: 2053,
  nationality: "ca",
  convoy: "HX-52",
  outcome: "damaged",
  lat: 50.5167,
  lng: -11.0833,
};

const details = {
  ship_type: "Steam merchant",
  completed: "1923 - Frazer Brace Ltd, Three Rivers PQ",
  owner: "Canada Steamship Lines Ltd, Montreal",
  homeport: "Montreal",
  nationality: "Canadian",
  fate: "Sunk by U-99 (Otto Kretschmer)",
  complement: "23 (0 dead and 23 survivors).",
  convoy: "HX-52 (straggler)",
  route: "Halifax (21 Jun) - Preston",
  cargo: "512 standards of timber",
  history: "Built as John C. Howard, later renamed Magog",
  notes: "At 12.51 hours",
};

test("shipFacts shows what the hit knows before the details arrive", () => {
  assert.deepEqual(shipFacts(hit, null), [
    ["Tonnage", "2.053 ton"],
    ["Datum", "1940-07-05"],
    ["Uitkomst", "beschadigd"],
    ["Positie", "50,517° N, 11,083° W"],
    ["Nationaliteit", "ca"],
    ["Konvooi", "HX-52"],
  ]);
});

test("shipFacts adds the details in order and prefers their nationality and convoy", () => {
  assert.deepEqual(shipFacts(hit, details), [
    ["Tonnage", "2.053 ton"],
    ["Datum", "1940-07-05"],
    ["Uitkomst", "beschadigd"],
    ["Positie", "50,517° N, 11,083° W"],
    ["Type", "Steam merchant"],
    ["Gebouwd", "1923 - Frazer Brace Ltd, Three Rivers PQ"],
    ["Eigenaar", "Canada Steamship Lines Ltd, Montreal"],
    ["Thuishaven", "Montreal"],
    ["Nationaliteit", "Canadian"],
    ["Lot", "Sunk by U-99 (Otto Kretschmer)"],
    ["Bemanning", "23 (0 dead and 23 survivors)."],
    ["Konvooi", "HX-52 (straggler)"],
    ["Route", "Halifax (21 Jun) - Preston"],
    ["Lading", "512 standards of timber"],
    ["Geschiedenis", "Built as John C. Howard, later renamed Magog"],
  ]);
});

test("shipFacts writes south and east, and says when the position is unknown", () => {
  const south = shipFacts({ ...hit, lat: -33.5, lng: 18 }, null);
  assert.deepEqual(south.find(([label]) => label === "Positie"), ["Positie", "33,500° S, 18,000° E"]);
  const unknown = shipFacts({ ...hit, lat: null, lng: null }, null);
  assert.deepEqual(unknown.find(([label]) => label === "Positie"), ["Positie", "onbekend"]);
});

test("shipFacts skips unknown details", () => {
  const labels = shipFacts({ ...hit, nationality: null, convoy: null }, { owner: "Acme", cargo: null }).map(([l]) => l);
  assert.deepEqual(labels, ["Tonnage", "Datum", "Uitkomst", "Positie", "Eigenaar"]);
});

test("otherHits leaves out the hit itself but keeps another hit by the same boat", () => {
  const same = { ...hit, date: "1940-07-08" };
  const other = { ...hit, boat_slug: "u100", boat_number: "U-100", date: "1940-07-09" };
  assert.deepEqual(otherHits(hit, [other, hit, same]), [same, other]);
});

test("hitLine names date, boat and outcome", () => {
  assert.equal(hitLine({ ...hit, outcome: "sunk" }), "1940-07-05 · U-99 · gezonken");
});

test("hitBy names the boat and sourceUrl points at the ship's page", () => {
  assert.equal(hitBy(hit), "Getroffen door U-99");
  assert.equal(sourceUrl("408"), "https://uboat.net/allies/merchants/ship/408.html");
});

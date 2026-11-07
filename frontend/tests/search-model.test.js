import { test } from "node:test";
import assert from "node:assert/strict";

import { matchBoats, matchShips, matchBattles } from "../js/search-model.js";

const boats = Array.from({ length: 8 }, (_, i) => ({ slug: `u${i}`, number: `U-${i}`, name: i === 0 ? "Der Wolf" : null }));
const ships = [
  { ship_external_id: "1", name: "Magog", boat_number: "U-99" },
  { ship_external_id: "1", name: "Magog", boat_number: "U-100" },
  { ship_external_id: "2", name: "Empire Magog", boat_number: "U-99" },
  ...Array.from({ length: 8 }, (_, i) => ({ ship_external_id: `x${i}`, name: `Ship ${i}`, boat_number: "U-1" })),
];
const battles = [
  { title: "Battle of Narvik", place: "Norway" },
  { title: "Kursk", place: "Near NARVIK" },
  { title: "Other", place: null },
  ...Array.from({ length: 8 }, (_, i) => ({ title: `Fight ${i}`, place: null })),
];

test("matchBoats finds number and name, ignoring case", () => {
  assert.deepEqual(matchBoats(boats, "u-3").map((r) => r.item.slug), ["u3"]);
  assert.deepEqual(matchBoats(boats, "WOLF").map((r) => r.item.slug), ["u0"]);
});

test("matchShips finds names and drops a repeated ship id", () => {
  const found = matchShips(ships, "magog");
  assert.deepEqual(found.map((r) => r.item.ship_external_id), ["1", "2"]);
});

test("matchBattles finds title and place", () => {
  const found = matchBattles(battles, "narvik");
  assert.deepEqual(found.map((r) => r.label), ["Battle of Narvik", "Kursk"]);
  assert.equal(found[1].sub, "Near NARVIK");
});

test("each matcher returns at most 5 rows of { label, sub, item }", () => {
  assert.equal(matchBoats(boats, "u-").length, 5);
  assert.equal(matchShips(ships, "ship").length, 5);
  assert.equal(matchBattles(battles, "fight").length, 5);
  assert.deepEqual(Object.keys(matchBoats(boats, "u-")[0]).sort(), ["item", "label", "sub"]);
});

test("an empty or blank query matches nothing", () => {
  for (const q of ["", "   ", null, undefined]) {
    assert.deepEqual(matchBoats(boats, q), []);
    assert.deepEqual(matchShips(ships, q), []);
    assert.deepEqual(matchBattles(battles, q), []);
  }
});

import { parseCoordinates } from "../js/search-model.js";

test("parseCoordinates reads decimal and degree notations", () => {
  assert.deepEqual(parseCoordinates("52.37, 4.89"), { lat: 52.37, lng: 4.89 });
  assert.deepEqual(parseCoordinates("52.37 4.89"), { lat: 52.37, lng: 4.89 });
  assert.deepEqual(parseCoordinates("-33.9, 151.2"), { lat: -33.9, lng: 151.2 });
  assert.deepEqual(parseCoordinates("51°59′N 5°55′E"), { lat: 51.98333, lng: 5.91667 });
  assert.deepEqual(parseCoordinates("54°24'26\"N 18°40'05\"E"), { lat: 54.40722, lng: 18.66806 });
  assert.deepEqual(parseCoordinates("12°S 77°W"), { lat: -12, lng: -77 });
  assert.deepEqual(parseCoordinates("N 52.5 E 13.4"), { lat: 52.5, lng: 13.4 });
});

test("parseCoordinates leaves names and impossible numbers alone", () => {
  for (const text of ["Narvik", "U-99", "1940", "95, 10", "10, 190", "52.37", "Slag om 1944 5", ""]) {
    assert.equal(parseCoordinates(text), null, text);
  }
});

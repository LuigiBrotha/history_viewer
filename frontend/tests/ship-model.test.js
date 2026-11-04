import { test } from "node:test";
import assert from "node:assert/strict";

import {
  mergeShips,
  shipStyle,
  shipTooltip,
  shipTotalsLine,
  shipsInPeriod,
  shipsUpToDate,
  shipsWithoutPosition,
} from "../js/ship-model.js";

const ship = (over = {}) => ({
  ship_external_id: "408",
  boat_slug: "u99",
  boat_number: "U-99",
  name: "Magog",
  date: "1940-07-05",
  tons: 2053,
  outcome: "sunk",
  lat: 50.5,
  lng: -11.1,
  ...over,
});

test("mergeShips replaces a hit by ship, boat and date and appends new ones", () => {
  const ships = [ship({ tons: 1 }), ship({ date: "1940-07-09", tons: 5 })];
  const merged = mergeShips(ships, [ship({ tons: 2 }), ship({ boat_slug: "u100", tons: 9 })]);
  assert.deepEqual(
    merged.map((s) => [s.boat_slug, s.date, s.tons]),
    [["u99", "1940-07-05", 2], ["u99", "1940-07-09", 5], ["u100", "1940-07-05", 9]],
  );
  assert.equal(ships[0].tons, 1);
});

test("shipsUpToDate includes a ship on its own date, not the day before", () => {
  const ships = [ship()];
  assert.equal(shipsUpToDate(ships, new Date("1940-07-05T00:00:00Z")).length, 1);
  assert.equal(shipsUpToDate(ships, new Date("1940-07-04T00:00:00Z")).length, 0);
  assert.equal(shipsUpToDate(ships, new Date("1941-01-01T00:00:00Z")).length, 1);
});

test("shipsUpToDate limits to the followed boat", () => {
  const ships = [ship(), ship({ boat_slug: "u100", ship_external_id: "9" })];
  const date = new Date("1940-08-01T00:00:00Z");
  assert.deepEqual(shipsUpToDate(ships, date, "u100").map((s) => s.boat_slug), ["u100"]);
  assert.equal(shipsUpToDate(ships, date, null).length, 2);
});

test("shipsInPeriod keeps the ships hit within the period, all without one", () => {
  const ships = [ship({ date: "1940-07-05" }), ship({ date: "1940-09-01", ship_external_id: "2" })];
  assert.equal(shipsInPeriod(ships, null, null).length, 2);
  assert.deepEqual(shipsInPeriod(ships, "1940-07-05", "1940-08-01").map((s) => s.date), ["1940-07-05"]);
  assert.deepEqual(shipsInPeriod(ships, "1940-08-01", null).map((s) => s.date), ["1940-09-01"]);
  assert.deepEqual(shipsInPeriod(ships, null, "1940-07-04"), []);
});

test("shipTotalsLine formats Dutch thousands and skips outcomes at zero", () => {
  const ships = [
    ship({ tons: 400000 }),
    ship({ tons: 12000, ship_external_id: "2" }),
    ship({ tons: 37965, outcome: "damaged", ship_external_id: "3" }),
  ];
  assert.equal(shipTotalsLine(ships), "2 gezonken (412.000 ton) · 1 beschadigd (37.965 ton)");
  assert.equal(shipTotalsLine([ship({ outcome: "captured", tons: 4000 })]), "1 buitgemaakt (4.000 ton)");
  assert.equal(shipTotalsLine([ship({ tons: 999 })]), "1 gezonken (999 ton)");
  assert.equal(shipTotalsLine([]), "");
});

test("shipTotalsLine counts a ship without a position", () => {
  const ships = [ship(), ship({ lat: null, lng: null, tons: 1000, ship_external_id: "2" })];
  assert.equal(shipTotalsLine(ships), "2 gezonken (3.053 ton)");
});

test("shipsWithoutPosition lists only ships that cannot be plotted", () => {
  const unknown = ship({ lat: null, lng: null, ship_external_id: "2" });
  assert.deepEqual(shipsWithoutPosition([ship(), unknown]), [unknown]);
});

test("shipTooltip names ship, tonnage, outcome, boat and date", () => {
  assert.equal(shipTooltip(ship()), "Magog — 2.053 ton — gezonken door U-99 op 1940-07-05");
  assert.equal(shipTooltip(ship({ outcome: "damaged" })), "Magog — 2.053 ton — beschadigd door U-99 op 1940-07-05");
  assert.equal(shipTooltip(ship({ outcome: "captured" })), "Magog — 2.053 ton — buitgemaakt door U-99 op 1940-07-05");
});

test("shipStyle distinguishes sunk, damaged and captured", () => {
  assert.deepEqual(shipStyle("sunk"), { color: "#222222", fillColor: "#222222", fillOpacity: 1 });
  assert.deepEqual(shipStyle("damaged"), { color: "#222222", fillColor: "#222222", fillOpacity: 0 });
  assert.deepEqual(shipStyle("captured"), { color: "#7a3db8", fillColor: "#7a3db8", fillOpacity: 1 });
});

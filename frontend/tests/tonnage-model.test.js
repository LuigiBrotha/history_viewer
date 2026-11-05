import { test } from "node:test";
import assert from "node:assert/strict";

import {
  boatSeries,
  colorSlots,
  nearestSeries,
  tonsOn,
  niceMax,
  tableRows,
  matchSeries,
} from "../js/tonnage-model.js";

const hit = (boat, date, tons, outcome = "sunk", name = "Ship") => ({
  boat_slug: boat,
  boat_number: boat.toUpperCase(),
  date,
  tons,
  outcome,
  name,
});

test("boatSeries adds up each boat's tonnage over time", () => {
  const [series] = boatSeries([hit("u1", "1940-02-01", 200), hit("u1", "1940-01-01", 100)]);
  assert.equal(series.slug, "u1");
  assert.equal(series.total, 300);
  assert.deepEqual(series.steps.map((step) => [step.date, step.total]), [
    ["1940-01-01", 100],
    ["1940-02-01", 300],
  ]);
});

test("boatSeries counts sunk and captured ships, not damaged ones", () => {
  const [series] = boatSeries([
    hit("u1", "1940-01-01", 100),
    hit("u1", "1940-01-02", 50, "captured"),
    hit("u1", "1940-01-03", 999, "damaged"),
  ]);
  assert.equal(series.total, 150);
  assert.equal(series.steps.length, 2);
});

test("boatSeries leaves out a boat with only damaged ships", () => {
  assert.deepEqual(boatSeries([hit("u1", "1940-01-01", 100, "damaged")]), []);
});

test("boatSeries sorts the biggest boat first and keeps two hits on one day apart", () => {
  const series = boatSeries([
    hit("small", "1940-01-01", 1),
    hit("big", "1940-01-01", 5, "sunk", "A"),
    hit("big", "1940-01-01", 5, "sunk", "B"),
  ]);
  assert.deepEqual(series.map((s) => s.slug), ["big", "small"]);
  assert.deepEqual(series[0].steps.map((step) => step.name), ["A", "B"]);
  assert.equal(series[0].total, 10);
});

test("colorSlots keeps a boat's colour when another boat grows past it", () => {
  const slots = new Map();
  const first = boatSeries([hit("a", "1940-01-01", 300), hit("b", "1940-01-01", 200)]);
  colorSlots(first, slots, 2);
  assert.deepEqual([...slots], [["a", 0], ["b", 1]]);

  const later = boatSeries([hit("c", "1940-01-01", 900), hit("a", "1940-01-01", 300), hit("b", "1940-01-01", 200)]);
  colorSlots(later, slots, 2);

  assert.equal(slots.get("a"), 0);
  assert.equal(slots.get("b"), 1);
  assert.equal(slots.has("c"), false);
});

test("tonsOn gives the running total of that day, and zero before the first ship", () => {
  const [series] = boatSeries([hit("u1", "1940-01-10", 100), hit("u1", "1940-02-10", 50)]);
  assert.equal(tonsOn(series, "1940-01-09"), 0);
  assert.equal(tonsOn(series, "1940-01-10"), 100);
  assert.equal(tonsOn(series, "1940-01-20"), 100);
  assert.equal(tonsOn(series, "1945-01-01"), 150);
});

test("nearestSeries picks the boat whose line is closest to the pointer's height", () => {
  const series = boatSeries([hit("a", "1940-01-01", 100), hit("b", "1940-01-01", 500)]);
  assert.equal(nearestSeries(series, "1940-02-01", 450).slug, "b");
  assert.equal(nearestSeries(series, "1940-02-01", 120).slug, "a");
});

test("nearestSeries finds nothing without series", () => {
  assert.equal(nearestSeries([], "1940-02-01", 10), null);
});

test("niceMax rounds up to a readable axis end", () => {
  assert.equal(niceMax(284759), 300000);
  assert.equal(niceMax(1200), 2000);
  assert.equal(niceMax(0), 1000);
});

test("tableRows lists boat, tonnage and number of ships in Dutch", () => {
  const rows = tableRows(boatSeries([hit("u1", "1940-01-10", 12345), hit("u1", "1940-02-10", 50)]));
  assert.deepEqual(rows, [{ slug: "u1", boat: "U1", tons: "12.395", ships: 2 }]);
});

test("matchSeries finds a boat by its number, ignoring the dash and case", () => {
  const series = [{ slug: "u99", number: "U-99" }, { slug: "u100", number: "U-100" }];
  assert.equal(matchSeries(series, "u99").slug, "u99");
  assert.equal(matchSeries(series, "U-100").slug, "u100");
  assert.equal(matchSeries(series, "99").slug, "u99");
  assert.equal(matchSeries(series, "nope"), null);
  assert.equal(matchSeries(series, ""), null);
});

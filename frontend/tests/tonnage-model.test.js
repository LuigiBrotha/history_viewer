import { test } from "node:test";
import assert from "node:assert/strict";

import {
  boatSeries,
  colorSlots,
  niceMax,
  tableRows,
  matchSeries,
  periodLabel,
  segmentAt,
  stackedBars,
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

function twoBoats() {
  return boatSeries([
    { boat_slug: "a", boat_number: "A", date: "1940-01-20", tons: 100, name: "One", outcome: "sunk" },
    { boat_slug: "a", boat_number: "A", date: "1940-03-02", tons: 50, name: "Two", outcome: "sunk" },
    { boat_slug: "b", boat_number: "B", date: "1940-02-10", tons: 30, name: "Three", outcome: "sunk" },
  ]);
}

test("stackedBars gives every month a bar, also a month in which nothing sank", () => {
  const empty = boatSeries([
    { boat_slug: "a", boat_number: "A", date: "1940-01-20", tons: 100, name: "One", outcome: "sunk" },
    { boat_slug: "a", boat_number: "A", date: "1940-03-02", tons: 50, name: "Two", outcome: "sunk" },
  ]);
  const bars = stackedBars(empty, "month");
  assert.deepEqual(bars.map((bar) => bar.period), ["1940-01-01", "1940-02-01", "1940-03-01"]);
  assert.deepEqual(bars.map((bar) => bar.total), [100, 100, 150]);
});

test("each bar stacks the running total of each boat, biggest boat at the bottom", () => {
  const bars = stackedBars(twoBoats(), "month");
  assert.deepEqual(bars[0].segments.map(({ slug, from, to }) => [slug, from, to]), [["a", 0, 100]]);
  assert.deepEqual(bars[1].segments.map(({ slug, from, to }) => [slug, from, to]), [["a", 0, 100], ["b", 100, 130]]);
  assert.deepEqual(bars[2].segments.map(({ slug, from, to }) => [slug, from, to]), [["a", 0, 150], ["b", 150, 180]]);
});

test("a segment names only the ships of its own period", () => {
  const [first, second, third] = stackedBars(twoBoats(), "month");
  assert.deepEqual(first.segments[0].ships, ["One"]);
  assert.equal(first.segments[0].added, 100);
  assert.deepEqual(second.segments[0].ships, []);
  assert.equal(second.segments[0].added, 0);
  assert.deepEqual(third.segments[0].ships, ["Two"]);
  assert.equal(third.segments[0].added, 50);
});

test("a week starts on Monday and a day is its own period", () => {
  const series = boatSeries([
    { boat_slug: "a", boat_number: "A", date: "1940-03-03", tons: 10, name: "Sunday", outcome: "sunk" },
    { boat_slug: "a", boat_number: "A", date: "1940-03-04", tons: 10, name: "Monday", outcome: "sunk" },
  ]);
  assert.deepEqual(stackedBars(series, "week").map((bar) => bar.period), ["1940-02-26", "1940-03-04"]);
  assert.deepEqual(stackedBars(series, "day").map((bar) => bar.period), ["1940-03-03", "1940-03-04"]);
});

test("stackedBars of nothing is no bars", () => {
  assert.deepEqual(stackedBars([], "month"), []);
});

test("segmentAt finds the boat at a height, and nothing above the bar", () => {
  const bar = stackedBars(twoBoats(), "month")[1];
  assert.equal(segmentAt(bar, 50).slug, "a");
  assert.equal(segmentAt(bar, 120).slug, "b");
  assert.equal(segmentAt(bar, 500), null);
});

test("periodLabel reads as Dutch text", () => {
  assert.equal(periodLabel("1941-03-01", "month"), "maart 1941");
  assert.equal(periodLabel("1941-03-03", "week"), "week van 3 maart 1941");
  assert.equal(periodLabel("1941-03-16", "day"), "16 maart 1941");
});

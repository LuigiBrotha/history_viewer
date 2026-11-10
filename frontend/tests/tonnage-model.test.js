import { test } from "node:test";
import assert from "node:assert/strict";

import {
  atSeaDays,
  barsFor,
  boatSeries,
  happyTimeOf,
  happyTimeSpans,
  inAmericanWaters,
  periodBars,
  ratePerBoatDay,
  colorSlots,
  niceMax,
  tableRows,
  matchSeries,
  periodLabel,
  segmentAt,
  stackedBars,
  barPosition,
  dotAt,
  outcomeLabel,
  shipDots,
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

test("per period a bar holds only what sank in that period", () => {
  const series = boatSeries([hit("u1", "1940-01-10", 100), hit("u1", "1940-03-10", 40), hit("u2", "1940-03-11", 60)]);
  const bars = periodBars(stackedBars(series, "month"));
  assert.deepEqual(bars.map((bar) => bar.total), [100, 0, 100]);
  assert.deepEqual(bars[2].segments.map(({ slug, from, to }) => [slug, from, to]), [["u1", 0, 40], ["u2", 40, 100]]);
  assert.equal(bars[1].segments.length, 0);
});

test("days at sea are counted per period, first and last day included", () => {
  const days = atSeaDays([{ departure_date: "1940-01-30", arrival_date: "1940-02-02" }, { departure_date: "1940-02-01", arrival_date: "1940-02-01" }], "month");
  assert.equal(days.get("1940-01-01"), 2);
  assert.equal(days.get("1940-02-01"), 3);
});

test("the yield of a period is its tonnage divided by the days the boats were at sea", () => {
  const series = boatSeries([hit("u1", "1940-01-10", 300), hit("u2", "1940-01-11", 100), hit("u1", "1940-02-10", 50)]);
  const bars = ratePerBoatDay(periodBars(stackedBars(series, "month")), new Map([["1940-01-01", 8]]));
  assert.equal(bars[0].total, 50);
  assert.equal(bars[0].boatDays, 8);
  assert.deepEqual(bars[0].segments.map(({ from, to }) => [from, to]), [[0, 37.5], [37.5, 50]]);
  assert.deepEqual(bars[1], { period: "1940-02-01", total: 0, boatDays: 0, segments: [] }, "no boat at sea, no yield");
});

test("American waters are west of 50 degrees west and south of Greenland", () => {
  assert.equal(inAmericanWaters({ lat: 35, lng: -75 }), true);
  assert.equal(inAmericanWaters({ lat: 10, lng: -61 }), true);
  assert.equal(inAmericanWaters({ lat: 55, lng: -20 }), false);
  assert.equal(inAmericanWaters({ lat: 60, lng: -55 }), false);
  assert.equal(inAmericanWaters({ lat: null, lng: null }), false);
});

test("the American view keeps the time axis of the whole war", () => {
  const ships = [
    { ...hit("u1", "1940-01-10", 100), lat: 50, lng: -10 },
    { ...hit("u2", "1942-03-10", 70), lat: 35, lng: -75 },
    { ...hit("u1", "1942-04-10", 10), lat: 50, lng: -10 },
  ];
  const bars = barsFor("amerika", { ships, series: boatSeries(ships), periods: [], unit: "month" });
  assert.equal(bars[0].period, "1940-01-01");
  assert.equal(bars.at(-1).period, "1942-04-01");
  assert.equal(bars.reduce((sum, bar) => sum + bar.total, 0), 70);
});

test("each view gives its own bars", () => {
  const ships = [hit("u1", "1940-01-10", 100), hit("u1", "1940-02-10", 50)];
  const input = { ships, series: boatSeries(ships), periods: [{ departure_date: "1940-02-01", arrival_date: "1940-02-05" }], unit: "month" };
  assert.deepEqual(barsFor("cumulatief", input).map((bar) => bar.total), [100, 150]);
  assert.deepEqual(barsFor("periode", input).map((bar) => bar.total), [100, 50]);
  assert.deepEqual(barsFor("rendement", input).map((bar) => bar.total), [0, 10]);
});

test("a Happy Time covers the bars of its months and is left out where it falls off the axis", () => {
  const months = ["1940-05-01", "1940-06-01", "1941-02-01", "1941-03-01"].map((period) => ({ period }));
  assert.deepEqual(happyTimeSpans(months, "month").map(({ name, first, last }) => [name, first, last]), [["First Happy Time", 1, 2]]);
});

test("a week that runs into a Happy Time belongs to it", () => {
  const weeks = [{ period: "1942-08-24" }, { period: "1942-08-31" }, { period: "1942-09-07" }];
  assert.deepEqual(happyTimeSpans(weeks, "week").map(({ first, last }) => [first, last]), [[0, 1]]);
  const before = [{ period: "1941-12-22" }, { period: "1941-12-29" }, { period: "1942-01-05" }];
  assert.deepEqual(happyTimeSpans(before, "week").map(({ first, last }) => [first, last]), [[1, 2]]);
});

test("the Happy Time of a bar is named in its tooltip", () => {
  assert.equal(happyTimeOf("1942-03-01", "month")?.name, "Second Happy Time");
  assert.equal(happyTimeOf("1943-03-01", "month"), null);
});

test("shipDots keeps every hit, damaged ones too; in American waters only those there", () => {
  const near = { ...hit("u1", "1942-01-20", 5000), lat: 35, lng: -75 };
  const far = { ...hit("u1", "1942-01-21", 6000, "damaged"), lat: 50, lng: -10 };
  assert.deepEqual(shipDots([near, far], "periode"), [near, far]);
  assert.deepEqual(shipDots([near, far], "cumulatief"), [near, far]);
  assert.deepEqual(shipDots([near, far], "amerika"), [near]);
});

const months = [{ period: "1940-01-01" }, { period: "1940-02-01" }, { period: "1940-03-01" }];

test("barPosition puts a date on the axis of the bars: its bar and how far through it", () => {
  assert.equal(barPosition("1940-01-01", months, "month"), 0);
  assert.equal(barPosition("1940-02-01", months, "month"), 1);
  assert.ok(Math.abs(barPosition("1940-01-16", months, "month") - 15 / 31) < 1e-9);
  assert.ok(Math.abs(barPosition("1940-03-31", months, "month") - (2 + 30 / 31)) < 1e-9);
});

test("barPosition keeps a date outside the bars at the edge of the axis, and has none without bars", () => {
  assert.equal(barPosition("1939-12-31", months, "month"), 0);
  assert.equal(barPosition("1940-04-02", months, "month"), 3);
  assert.equal(barPosition("1940-01-01", [], "month"), null);
});

test("barPosition follows the bars of a week", () => {
  const weeks = [{ period: "1940-01-01" }, { period: "1940-01-08" }];
  assert.ok(Math.abs(barPosition("1940-01-10", weeks, "week") - (1 + 2 / 7)) < 1e-9);
});

test("dotAt finds the nearest dot within reach, and nothing beyond it", () => {
  const dots = [{ x: 10, y: 10, ship: "a" }, { x: 14, y: 10, ship: "b" }];
  assert.equal(dotAt(dots, 13, 10, 8).ship, "b");
  assert.equal(dotAt(dots, 10, 19, 8), null);
  assert.equal(dotAt([], 1, 1, 8), null);
});

test("outcomeLabel gives each outcome in Dutch", () => {
  assert.equal(outcomeLabel("sunk"), "Gezonken");
  assert.equal(outcomeLabel("captured"), "Buitgemaakt");
  assert.equal(outcomeLabel("damaged"), "Beschadigd");
});

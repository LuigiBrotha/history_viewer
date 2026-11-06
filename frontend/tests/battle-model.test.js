import { test } from "node:test";
import assert from "node:assert/strict";

import {
  activeOn,
  applyPositions,
  wrapLng,
  barPosition,
  durationDays,
  durationText,
  filterBattles,
  labelsToShow,
  overlaps,
  squaresToDraw,
  withoutPosition,
} from "../js/battle-model.js";

const battle = (over = {}) => ({
  title: "Battle of Kursk",
  start: "1943-07-05",
  end: "1943-08-23",
  precision: "day",
  date_text: "5 July – 23 August 1943",
  lat: 51.7,
  lng: 36.1,
  part_of: "the Eastern Front of World War II",
  place: "Kursk, Soviet Union",
  ...over,
});

test("overlaps is true when the battle touches the period, ends included", () => {
  const b = battle();
  assert.equal(overlaps(b, "1943-08-23", "1943-09-01"), true);
  assert.equal(overlaps(b, "1943-06-01", "1943-07-05"), true);
  assert.equal(overlaps(b, "1943-07-10", "1943-07-11"), true);
  assert.equal(overlaps(b, "1943-08-24", "1943-09-01"), false);
  assert.equal(overlaps(b, "1943-01-01", "1943-07-04"), false);
});

test("overlaps treats a missing end of the period as open", () => {
  assert.equal(overlaps(battle(), null, null), true);
  assert.equal(overlaps(battle(), "1943-08-01", null), true);
  assert.equal(overlaps(battle(), null, "1943-07-01"), false);
});

test("activeOn keeps battles whose first to last day holds the date", () => {
  const kursk = battle();
  const midway = battle({ title: "Midway", start: "1942-06-04", end: "1942-06-07" });
  assert.deepEqual(activeOn([kursk, midway], "1942-06-07").map((b) => b.title), ["Midway"]);
  assert.deepEqual(activeOn([kursk, midway], "1942-06-08"), []);
  assert.deepEqual(activeOn([kursk, midway], "1943-07-05").map((b) => b.title), ["Battle of Kursk"]);
});

test("durationDays counts the first and last day", () => {
  assert.equal(durationDays(battle({ start: "1941-12-07", end: "1941-12-07" })), 1);
  assert.equal(durationDays(battle({ start: "1942-06-04", end: "1942-06-07" })), 4);
});

test("durationText is Dutch and picks days, months or years", () => {
  const span = (start, end, precision = "day") => durationText(battle({ start, end, precision }));
  assert.equal(span("1941-12-07", "1941-12-07"), "1 dag");
  assert.equal(span("1943-07-05", "1943-08-20"), "47 dagen");
  assert.equal(span("1943-07-05", "1943-08-23"), "50 dagen");
  assert.equal(span("1943-01-01", "1943-03-01"), "60 dagen");
  assert.equal(span("1943-01-01", "1943-03-02"), "2 maanden");
  assert.equal(span("1942-06-22", "1942-11-22"), "5 maanden");
  assert.equal(span("1942-01-01", "1942-01-31", "month"), "ongeveer 31 dagen");
  assert.equal(span("1939-09-03", "1945-05-08"), "6 jaar");
  assert.equal(span("1940-06-01", "1942-05-31"), "2 jaar");
  assert.equal(span("1940-06-01", "1942-04-30"), "23 maanden");
});

test("durationText says one month and one day in the singular", () => {
  assert.equal(durationText(battle({ start: "1943-01-01", end: "1943-01-01" })), "1 dag");
  assert.equal(durationText(battle({ start: "1943-01-01", end: "1943-02-10" })), "41 dagen");
});

test("a month-precision battle is announced as approximate", () => {
  assert.equal(durationText(battle({ start: "1942-06-01", end: "1942-08-31", precision: "month" })), "ongeveer 3 maanden");
});

test("filterBattles matches title, place and part_of, ignoring case", () => {
  const list = [
    battle(),
    battle({ title: "Midway", place: "Midway Atoll", part_of: "the Pacific War" }),
    battle({ title: "Nameless", place: null, part_of: null }),
  ];
  assert.deepEqual(filterBattles(list, "KURSK").map((b) => b.title), ["Battle of Kursk"]);
  assert.deepEqual(filterBattles(list, "atoll").map((b) => b.title), ["Midway"]);
  assert.deepEqual(filterBattles(list, " pacific ").map((b) => b.title), ["Midway"]);
  assert.deepEqual(filterBattles(list, "").length, 3);
  assert.deepEqual(filterBattles(list, "   ").length, 3);
  assert.deepEqual(filterBattles(list, "zzz"), []);
});

const BOUNDS = { min: "1939-01-01", max: "1945-12-31" };

test("barPosition gives left and width in percent of the axis", () => {
  const whole = barPosition(battle({ start: "1939-01-01", end: "1945-12-31" }), BOUNDS);
  assert.equal(whole.left, 0);
  assert.ok(Math.abs(whole.width - 100) < 1e-9);
  const middle = barPosition(battle({ start: "1942-07-02", end: "1942-07-02" }), BOUNDS);
  assert.ok(Math.abs(middle.left - 50) < 1);
});

test("barPosition keeps even a one-day battle visible and inside the axis", () => {
  const day = barPosition(battle({ start: "1941-12-07", end: "1941-12-07" }), BOUNDS);
  assert.ok(day.width >= 0.5);
  const last = barPosition(battle({ start: "1945-12-31", end: "1945-12-31" }), BOUNDS);
  assert.ok(last.left + last.width <= 100 + 1e-9);
});

test("barPosition clamps a battle that starts before the axis", () => {
  const early = barPosition(battle({ start: "1938-01-01", end: "1939-12-31" }), BOUNDS);
  assert.equal(early.left, 0);
  assert.ok(early.width > 0 && early.width < 20);
});

const view = { south: 40, west: -20, north: 60, east: 40 };

test("squaresToDraw keeps battles with a position in view, longest first", () => {
  const list = [
    battle({ title: "short", start: "1940-01-01", end: "1940-01-02" }),
    battle({ title: "long", start: "1940-01-01", end: "1940-03-01" }),
    battle({ title: "outside", lat: -30, lng: 20 }),
    battle({ title: "nowhere", lat: null, lng: null }),
    battle({ title: "east", lng: 41 }),
  ];
  assert.deepEqual(squaresToDraw(list, view).map((b) => b.title), ["long", "short"]);
});

test("squaresToDraw draws every battle in view, however many there are", () => {
  const list = Array.from({ length: 1000 }, (_, i) => battle({ title: `battle ${i}` }));
  assert.equal(squaresToDraw(list, view).length, 1000);
});

test("squaresToDraw breaks ties on the title so the set is stable", () => {
  const list = [battle({ title: "b" }), battle({ title: "a" })];
  assert.deepEqual(squaresToDraw(list, view).map((b) => b.title), ["a", "b"]);
});

test("labelsToShow names few squares at any zoom and many only when zoomed in", () => {
  const many = (n) => Array.from({ length: n }, (_, i) => battle({ title: `b${i}` }));
  assert.equal(labelsToShow(many(25), 3).length, 25);
  assert.deepEqual(labelsToShow(many(26), 3), []);
  assert.equal(labelsToShow(many(100), 6).length, 100);
  assert.deepEqual(labelsToShow(many(100), 5), []);
});

import { AXIS_BOUNDS, bandPosition, datePosition, yearMarks } from "../js/battle-model.js";

test("the axis runs over the war, from September 1939 to September 1945", () => {
  assert.deepEqual(AXIS_BOUNDS, { min: "1939-09-01", max: "1945-09-02" });
});

test("datePosition is a fraction of the axis, held inside it", () => {
  assert.equal(datePosition("1939-09-01", AXIS_BOUNDS), 0);
  assert.ok(Math.abs(datePosition("1945-09-02", AXIS_BOUNDS) - 1) < 0.001);
  assert.equal(datePosition("1930-01-01", AXIS_BOUNDS), 0);
  assert.equal(datePosition("1950-01-01", AXIS_BOUNDS), 1);
  assert.ok(Math.abs(datePosition("1942-09-01", AXIS_BOUNDS) - 0.5) < 0.01);
});

test("bandPosition shades a period, open ends reaching the edge of the axis", () => {
  assert.deepEqual(bandPosition(null, null, AXIS_BOUNDS), { from: 0, to: 1 });
  const band = bandPosition("1942-09-01", null, AXIS_BOUNDS);
  assert.ok(Math.abs(band.from - 0.5) < 0.01);
  assert.equal(band.to, 1);
  assert.equal(bandPosition(null, "1930-01-01", AXIS_BOUNDS).to, 0);
});

test("yearMarks gives the first year at the start and each new year at its January", () => {
  const marks = yearMarks(AXIS_BOUNDS);
  assert.deepEqual(marks.map((m) => m.year), [1939, 1940, 1941, 1942, 1943, 1944, 1945]);
  assert.equal(marks[0].fraction, 0);
  assert.ok(Math.abs(marks[1].fraction - 122 / 2194) < 0.001);
  assert.ok(marks.every((m, i) => i === 0 || m.fraction > marks[i - 1].fraction));
});

const posBattle = (title, lat = null, lng = null) => ({ title, start: "1940-01-01", end: "1940-01-02", lat, lng });

test("applyPositions gives a battle without a file position its Eigen positie", () => {
  const [result] = applyPositions([posBattle("A")], [{ title: "A", lat: 1, lng: 2 }]);
  assert.deepEqual([result.lat, result.lng, result.own, result.wikiLat, result.wikiLng], [1, 2, true, null, null]);
});

test("applyPositions overrides a file position and keeps it as wikiLat/wikiLng", () => {
  const [result] = applyPositions([posBattle("A", 10, 20)], [{ title: "A", lat: 1, lng: 2 }]);
  assert.deepEqual([result.lat, result.lng, result.own, result.wikiLat, result.wikiLng], [1, 2, true, 10, 20]);
});

test("applyPositions leaves other battles alone and ignores unknown titles", () => {
  const [result] = applyPositions([posBattle("A", 10, 20)], [{ title: "Z", lat: 1, lng: 2 }]);
  assert.deepEqual([result.lat, result.lng, result.wikiLat, result.wikiLng], [10, 20, 10, 20]);
  assert.equal(result.own, undefined);
});

test("applyPositions does not mutate its input", () => {
  const input = [posBattle("A", 10, 20)];
  applyPositions(input, [{ title: "A", lat: 1, lng: 2 }]);
  assert.deepEqual(input, [posBattle("A", 10, 20)]);
});

test("wrapLng brings a longitude into [-180, 180]", () => {
  assert.equal(wrapLng(190), -170);
  assert.equal(wrapLng(-190), 170);
  assert.equal(wrapLng(45), 45);
  assert.ok([180, -180].includes(wrapLng(540)));
});

test("withoutPosition keeps battles with no position, active on the date or in the period, matching the query", () => {
  const list = [
    battle({ title: "Placed", lat: 1, lng: 2 }),
    battle({ title: "Lost A", lat: null, lng: null, start: "1942-01-01", end: "1942-12-31", place: "Sea" }),
    battle({ title: "Half", lat: 5, lng: null, start: "1942-01-01", end: "1942-12-31" }),
    battle({ title: "Lost B", lat: null, lng: null, start: "1944-01-01", end: "1944-02-01", place: "Sea" }),
  ];
  const titles = (rows) => rows.map((b) => b.title);
  assert.deepEqual(titles(withoutPosition(list, "date", { date: "1942-06-01" }, "")), ["Lost A", "Half"]);
  assert.deepEqual(titles(withoutPosition(list, "date", { date: "1944-01-15" }, "")), ["Lost B"]);
  assert.deepEqual(titles(withoutPosition(list, "period", { from: "1942-06-01", to: "1944-01-01" }, "")), ["Lost A", "Half", "Lost B"]);
  assert.deepEqual(titles(withoutPosition(list, "period", { from: null, to: null }, "")), ["Lost A", "Half", "Lost B"]);
  assert.deepEqual(titles(withoutPosition(list, "period", { from: null, to: null }, "sea")), ["Lost A", "Lost B"]);
  assert.deepEqual(titles(withoutPosition(list, "date", null, "")), ["Lost A", "Half", "Lost B"]);
});

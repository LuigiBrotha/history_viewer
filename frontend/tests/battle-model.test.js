import { test } from "node:test";
import assert from "node:assert/strict";

import {
  activeOn,
  barPosition,
  durationDays,
  durationText,
  filterBattles,
  labelsToShow,
  overlaps,
  squaresToDraw,
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
  assert.deepEqual(squaresToDraw(list, view, 10).map((b) => b.title), ["long", "short"]);
});

test("squaresToDraw caps the count and keeps the longest", () => {
  const list = ["a", "b", "c", "d"].map((title, i) => battle({ title, start: "1940-01-01", end: `1940-01-0${i + 1}` }));
  assert.deepEqual(squaresToDraw(list, view, 2).map((b) => b.title), ["d", "c"]);
  assert.deepEqual(squaresToDraw(list, view, 0), []);
});

test("squaresToDraw breaks ties on the title so the set is stable", () => {
  const list = [battle({ title: "b" }), battle({ title: "a" })];
  assert.deepEqual(squaresToDraw(list, view, 5).map((b) => b.title), ["a", "b"]);
});

test("labelsToShow names few squares at any zoom and many only when zoomed in", () => {
  const many = (n) => Array.from({ length: n }, (_, i) => battle({ title: `b${i}` }));
  assert.equal(labelsToShow(many(25), 3).length, 25);
  assert.deepEqual(labelsToShow(many(26), 3), []);
  assert.equal(labelsToShow(many(100), 6).length, 100);
  assert.deepEqual(labelsToShow(many(100), 5), []);
});

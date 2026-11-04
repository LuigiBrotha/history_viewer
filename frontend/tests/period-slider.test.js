import { test } from "node:test";
import assert from "node:assert/strict";

import {
  dayNumber,
  isoFromDay,
  fractionForDay,
  dayForFraction,
  moveHandle,
  moveWindow,
  resolveHandle,
  selectionToPeriod,
  growSelection,
  yearTicks,
} from "../js/period-slider.js";

const bounds = { min: dayNumber("1940-01-01"), max: dayNumber("1945-01-01") };
const day = dayNumber;

test("dayNumber and isoFromDay are inverses", () => {
  assert.equal(isoFromDay(dayNumber("1941-03-15")), "1941-03-15");
  assert.equal(dayNumber("1941-03-16") - dayNumber("1941-03-15"), 1);
});

test("fractionForDay and dayForFraction map the slider ends onto the bounds", () => {
  assert.equal(fractionForDay(bounds.min, bounds), 0);
  assert.equal(fractionForDay(bounds.max, bounds), 1);
  assert.equal(dayForFraction(0, bounds), bounds.min);
  assert.equal(dayForFraction(1, bounds), bounds.max);
});

test("dayForFraction clamps a drag beyond the track", () => {
  assert.equal(dayForFraction(-0.5, bounds), bounds.min);
  assert.equal(dayForFraction(1.5, bounds), bounds.max);
});

test("fractionForDay is zero when all patrols share one day", () => {
  assert.equal(fractionForDay(bounds.min, { min: bounds.min, max: bounds.min }), 0);
});

test("moveHandle keeps the start from passing the end, and the other way round", () => {
  const selection = { from: day("1941-01-01"), to: day("1942-01-01") };
  assert.equal(moveHandle(selection, "from", day("1943-01-01"), bounds).from, selection.to);
  assert.equal(moveHandle(selection, "to", day("1940-06-01"), bounds).to, selection.from);
  assert.deepEqual(moveHandle(selection, "from", day("1941-02-01"), bounds), {
    from: day("1941-02-01"),
    to: selection.to,
  });
});

test("moveWindow shifts the period and keeps its length at the edges", () => {
  const selection = { from: day("1941-01-01"), to: day("1941-07-01") };
  const length = selection.to - selection.from;
  assert.deepEqual(moveWindow(selection, 10, bounds), { from: selection.from + 10, to: selection.to + 10 });

  const atStart = moveWindow(selection, -100000, bounds);
  assert.equal(atStart.from, bounds.min);
  assert.equal(atStart.to - atStart.from, length);

  const atEnd = moveWindow(selection, 100000, bounds);
  assert.equal(atEnd.to, bounds.max);
  assert.equal(atEnd.to - atEnd.from, length);
});

test("resolveHandle separates two stacked handles by drag direction", () => {
  const stacked = { from: day("1941-01-01"), to: day("1941-01-01") };
  assert.equal(resolveHandle("to", stacked, -1), "from");
  assert.equal(resolveHandle("from", stacked, 1), "to");
  const apart = { from: day("1941-01-01"), to: day("1941-02-01") };
  assert.equal(resolveHandle("to", apart, -1), "to");
});

test("selectionToPeriod is open at an end that sits on the bound", () => {
  assert.deepEqual(selectionToPeriod({ from: bounds.min, to: bounds.max }, bounds), { from: null, to: null });
  assert.deepEqual(selectionToPeriod({ from: day("1941-01-01"), to: bounds.max }, bounds), {
    from: "1941-01-01",
    to: null,
  });
  assert.deepEqual(selectionToPeriod({ from: bounds.min, to: day("1941-01-01") }, bounds), {
    from: null,
    to: "1941-01-01",
  });
});

test("growSelection follows new bounds only where the selection sat on the old edge", () => {
  const wider = { min: day("1939-01-01"), max: day("1946-01-01") };
  assert.deepEqual(growSelection({ from: bounds.min, to: bounds.max }, bounds, wider), {
    from: wider.min,
    to: wider.max,
  });
  const inner = { from: day("1941-01-01"), to: day("1942-01-01") };
  assert.deepEqual(growSelection(inner, bounds, wider), inner);
});

test("yearTicks marks each January first inside the bounds", () => {
  const ticks = yearTicks({ min: day("1939-08-19"), max: day("1942-03-12") });
  assert.deepEqual(ticks.map((tick) => tick.year), [1940, 1941, 1942]);
  assert.ok(ticks.every((tick) => tick.fraction > 0 && tick.fraction < 1));
});

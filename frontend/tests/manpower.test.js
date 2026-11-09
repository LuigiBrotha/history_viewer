import { test } from "node:test";
import assert from "node:assert/strict";

import {
  manpowerOf, lossesOf, bandStops, bandSteps, highestManpower, widthOf, stopText, clampBandWidth,
} from "../js/manpower.js";

const table = {
  A: { soldaten: 7500, tanks: [{ type: null, aantal: 225, bemanning: 3 }], vliegtuigen: [],
       verliezen: { manschappen: 750, tanks: [{ type: null, aantal: 37, bemanning: 3 }], vliegtuigen: [] },
       tekst: "225 tanks; 5,000-10,000 infantry", overgenomen_van: null },
  L: { soldaten: 160000, tanks: [{ type: null, aantal: 882, bemanning: 3 }], vliegtuigen: [], verliezen: null, tekst: "x", overgenomen_van: null },
  B: { soldaten: null, tanks: [], vliegtuigen: [], verliezen: null, tekst: "y", overgenomen_van: "L" },
  M: { soldaten: null, tanks: [{ type: null, aantal: 100, bemanning: 3 }], vliegtuigen: [], verliezen: null, tekst: "100 tanks", overgenomen_van: null },
  N: { soldaten: null, tanks: [], vliegtuigen: [], verliezen: null, tekst: "z", overgenomen_van: "M" },
  P: { soldaten: 1000, tanks: [], vliegtuigen: [{ type: null, aantal: 10, bemanning: 3 }],
       verliezen: { manschappen: 5, tanks: [], vliegtuigen: [] }, tekst: "p", overgenomen_van: "L" },
  Q: { soldaten: 1000, tanks: [], vliegtuigen: [{ type: null, aantal: 10, bemanning: 3 }],
       verliezen: null, tekst: "q", overgenomen_van: null },
};
const stopFor = (title) => bandStops([{ title }], table)[0];

test("Manschappen are soldiers plus crews", () => {
  const m = manpowerOf("A", table);
  assert.equal(m.total, 8175);
  assert.deepEqual([m.soldiers, m.tanks, m.aircraft, m.borrowedFrom], [7500, 675, 0, null]);
});
test("tanks alone are not a figure", () => assert.equal(manpowerOf("M", table), null));
test("an unknown title is not a figure", () => assert.equal(manpowerOf("nope", table), null));
test("a borrowed figure names its source", () => assert.deepEqual(
  [manpowerOf("B", table).total, manpowerOf("B", table).borrowedFrom], [162646, "L"]));
test("a lender without soldiers or a missing lender gives null", () => {
  assert.equal(manpowerOf("N", table), null);
  assert.equal(manpowerOf("X", { X: { ...table.B, overgenomen_van: "gone" } }), null);
});
test("losses are counted with crews and never borrowed", () => {
  assert.equal(lossesOf("A", table), 861);
  assert.equal(lossesOf("B", table), null);
  assert.equal(lossesOf("nope", table), null);
});
test("a battle that borrows its strength keeps its own losses", () => {
  assert.equal(lossesOf("P", table), 5);
});
test("a step needs a figure on both ends to be solid", () => {
  const stops = bandStops([{ title: "A" }, { title: "L" }, { title: "M" }], table);
  const steps = bandSteps(stops);
  assert.equal(steps.length, 2);
  assert.deepEqual(steps.map((s) => s.solid), [true, false]);
  assert.equal(steps[0].from, stops[0]);
  assert.equal(steps[0].to, stops[1]);
});
test("a Veldslag that is not in the file becomes a dotted stop", () => {
  const stop = stopFor("nope");
  assert.equal(stop.manpower, null);
  assert.equal(stop.entry, null);
  assert.equal(stop.loss, null);
});
test("bandStops carries manpower, loss and entry", () => {
  const stop = stopFor("A");
  assert.equal(stop.manpower.total, 8175);
  assert.equal(stop.loss, 861);
  assert.equal(stop.entry, table.A);
  assert.equal(stop.battle.title, "A");
});
test("the highest figure is taken over stops with a figure, 0 without", () => {
  assert.equal(highestManpower(bandStops([{ title: "A" }, { title: "L" }, { title: "M" }], table)), 162646);
  assert.equal(highestManpower(bandStops([{ title: "M" }], table)), 0);
  assert.equal(highestManpower([]), 0);
});
test("the highest figure gets the full width and the rest is linear", () => {
  assert.equal(widthOf(162646, 162646, 48), 48);
  assert.ok(Math.abs(widthOf(8175, 162646, 48) - 2.4126) < 0.001);
  assert.equal(widthOf(100, 0, 48), 0);
});
test("the tooltip gives the build-up, the original text and the source of a borrowed figure", () => {
  assert.equal(stopText(stopFor("A")), [
    "A", "8.175 Manschappen", "7.500 soldaten", "225 tanks × 3",
    "Hele kant, niet alleen de eigen troepen", "Verlies: 861", "225 tanks; 5,000-10,000 infantry",
  ].join("\n"));
  const borrowed = stopText(stopFor("B")).split("\n");
  assert.ok(borrowed.includes("cijfer van L"));
  assert.ok(borrowed.includes("162.646 Manschappen"));
  assert.equal(borrowed.at(-1), "y");
});
test("the tooltip uses title_en first and lists aircraft", () => {
  const stop = bandStops([{ title: "Q", title_en: "Plane" }], table)[0];
  const lines = stopText(stop).split("\n");
  assert.equal(lines[0], "Plane");
  assert.ok(lines.includes("10 vliegtuigen × 3"));
});
test("a stop without a figure says so and keeps the original text", () => {
  assert.equal(stopText(stopFor("M")), "M\nGeen aantal soldaten\n100 tanks");
  assert.equal(stopText(stopFor("nope")), "nope\nGeen aantal soldaten");
});

test("clampBandWidth accepts whole numbers from 8 to 96 and nothing else", () => {
  assert.equal(clampBandWidth(48), 48);
  assert.equal(clampBandWidth("64"), 64);
  assert.equal(clampBandWidth(8), 8);
  assert.equal(clampBandWidth(96), 96);
  for (const bad of [0, 7, 97, 9999, "0", "9999", "abc", "", null, undefined, 12.5, "12.5", NaN])
    assert.equal(clampBandWidth(bad), undefined, String(bad));
});

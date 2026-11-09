import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const FIGURES = read("../battles/manschappen.json")["Erwin Rommel"];
const BATTLES = read("../battles/battles.json");

const STEPS = [
  "Battle of Arras (1940)", "Siege of Lille (1940)", "Combat de Pont-de-l'Arche",
  "Raid on Bardia", "Operation Brevity", "Operation Battleaxe", "Operation Flipper",
  "Operation Crusader", "Battle of Bir Hakeim", "Axis capture of Tobruk",
  "Battle of Mersa Matruh", "First Battle of El Alamein", "Battle of Alam el Halfa",
  "Second Battle of El Alamein", "Battle of El Agheila", "Battle of Tripoli (1943)",
  "Battle of Kasserine Pass", "Battle of Medenine", "Operation Achse", "Lądowanie w Normandii",
];
const LENDERS = { "Siege of Tobruk": 35000, "Battle of Gazala": 90000 };
const BORROWERS = {
  "Raid on Bardia": "Siege of Tobruk", "Operation Brevity": "Siege of Tobruk",
  "Operation Battleaxe": "Siege of Tobruk", "Operation Flipper": "Siege of Tobruk",
  "Axis capture of Tobruk": "Battle of Gazala",
};
const DOTTED = [
  "Combat de Pont-de-l'Arche", "Battle of Mersa Matruh", "Battle of Alam el Halfa",
  "Battle of Tripoli (1943)", "Battle of Medenine", "Operation Achse", "Lądowanie w Normandii",
];

test("every step of Rommel's Spoor is in the file and names a real Veldslag", () => {
  const known = new Set(BATTLES.map((b) => b.title));
  assert.equal(STEPS.length, 20);
  for (const title of [...STEPS, ...Object.keys(LENDERS)]) {
    assert.ok(FIGURES[title], `${title} missing from manschappen.json`);
    assert.ok(known.has(title), `${title} is not in battles.json`);
  }
  assert.equal(Object.keys(FIGURES).length, STEPS.length + Object.keys(LENDERS).length);
});

test("own figures are as in the infobox", () => {
  const own = {
    "Battle of Arras (1940)": 7500, "Siege of Lille (1940)": 160000, "Operation Crusader": 119000,
    "Battle of Bir Hakeim": 41000, "First Battle of El Alamein": 96000,
    "Second Battle of El Alamein": 116000, "Battle of El Agheila": 60000, "Battle of Kasserine Pass": 22000,
  };
  for (const [title, soldiers] of Object.entries(own)) {
    assert.equal(FIGURES[title].soldaten, soldiers, title);
    assert.equal(FIGURES[title].overgenomen_van, null, title);
  }
  const arras = FIGURES["Battle of Arras (1940)"];
  assert.equal(arras.tanks.reduce((n, l) => n + l.aantal, 0), 225);
  assert.deepEqual(arras.verliezen, { manschappen: 750, tanks: 37, vliegtuigen: 0 });
  assert.equal(FIGURES["Siege of Lille (1940)"].verliezen, null);
  assert.deepEqual(FIGURES["Battle of Bir Hakeim"].verliezen, { manschappen: 3836, tanks: 0, vliegtuigen: 49 });
});

test("only these battles borrow, and only from real battles", () => {
  for (const [title, entry] of Object.entries(FIGURES)) {
    const lender = BORROWERS[title] ?? null;
    assert.equal(entry.overgenomen_van, lender, title);
    if (lender) {
      assert.equal(entry.soldaten, null, title);
      assert.ok(FIGURES[lender], `${lender} is not in the file`);
    }
  }
  for (const [title, soldiers] of Object.entries(LENDERS)) assert.equal(FIGURES[title].soldaten, soldiers);
});

test("dotted battles have no soldiers and do not borrow", () => {
  for (const title of DOTTED) {
    assert.equal(FIGURES[title].soldaten, null, title);
    assert.equal(FIGURES[title].overgenomen_van, null, title);
  }
});

test("every tank and aircraft line has a crew and every Veldslag its original text", () => {
  for (const [title, entry] of Object.entries(FIGURES)) {
    assert.ok([1, 2].includes(entry.kolom), title);
    assert.ok(entry.tekst && entry.tekst.length > 0, `${title} has no text`);
    assert.doesNotMatch(entry.tekst, /<ref|\{\{|\}\}|<br/, `${title} text has markup`);
    assert.ok(entry.bron, title);
    for (const line of [...entry.tanks, ...entry.vliegtuigen]) {
      assert.ok(Number.isInteger(line.bemanning) && line.bemanning > 0, `${title} crew`);
      assert.ok(Number.isFinite(line.aantal) && line.aantal >= 0, `${title} count`);
      assert.ok(line.bron, `${title} line source`);
      if (line.type === null) assert.equal(line.bemanning, 3, `${title} untyped crew`);
    }
    if (entry.verliezen) assert.ok(Number.isFinite(entry.verliezen.manschappen), title);
  }
});

const total = (lines) => lines.reduce((n, l) => n + l.aantal, 0);
const split = (lines) => lines.map((l) => [l.type, l.aantal, l.bemanning]);

test("Operation Crusader figures", () => {
  const e = FIGURES["Operation Crusader"];
  assert.equal(total(e.tanks), 483);
  assert.deepEqual(split(e.tanks), [
    ["Panzer II", 70, 3], ["Panzer III", 139, 5], ["Panzer IV", 35, 5], ["Fiat M13/40", 146, 4], [null, 93, 3],
  ]);
  assert.equal(total(e.vliegtuigen), 536);
  assert.deepEqual(e.verliezen, { manschappen: 52100, tanks: 340, vliegtuigen: 332 });
});

test("Second Battle of El Alamein figures", () => {
  const e = FIGURES["Second Battle of El Alamein"];
  assert.equal(total(e.tanks), 547);
  assert.equal(total(e.vliegtuigen), 835);
  assert.deepEqual(e.verliezen, { manschappen: 57400, tanks: 500, vliegtuigen: 84 });
});

test("losses and strengths of the other battles", () => {
  const battleaxe = FIGURES["Operation Battleaxe"];
  assert.deepEqual(battleaxe.tanks.map((l) => l.aantal), [100, 96]);
  assert.deepEqual(battleaxe.vliegtuigen.map((l) => l.aantal), [130, 84]);
  assert.deepEqual(battleaxe.verliezen, { manschappen: 1270, tanks: 12, vliegtuigen: 10 });
  const gazala = FIGURES["Battle of Gazala"];
  assert.equal(gazala.soldaten, 90000);
  assert.equal(total(gazala.tanks), 560);
  assert.equal(total(gazala.vliegtuigen), 542);
  assert.equal(gazala.verliezen.manschappen, 6360);
  assert.equal(gazala.verliezen.tanks, 125);
  assert.equal(FIGURES["Battle of Medenine"].verliezen.manschappen, 635);
  assert.equal(FIGURES["Battle of Medenine"].verliezen.tanks, 47);
  assert.deepEqual(FIGURES["Battle of Alam el Halfa"].verliezen, { manschappen: 2900, tanks: 49, vliegtuigen: 36 });
});

test("Siege of Tobruk has no aircraft strength line, its aircraft are losses", () => {
  const e = FIGURES["Siege of Tobruk"];
  assert.deepEqual(e.vliegtuigen, []);
  assert.equal(e.verliezen.vliegtuigen, 112);
});

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
  assert.deepEqual(lost(arras), [750, 37, 0]);
  assert.equal(FIGURES["Siege of Lille (1940)"].verliezen, null);
  assert.deepEqual(lost(FIGURES["Battle of Bir Hakeim"]), [3836, 0, 49]);
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
const lost = (e) => [e.verliezen.manschappen, total(e.verliezen.tanks), total(e.verliezen.vliegtuigen)];
const split = (lines) => lines.map((l) => [l.type, l.aantal, l.bemanning]);

test("Operation Crusader figures", () => {
  const e = FIGURES["Operation Crusader"];
  assert.equal(total(e.tanks), 483);
  assert.deepEqual(split(e.tanks), [
    ["Panzer II", 70, 3], ["Panzer III", 139, 5], ["Panzer IV", 35, 5], ["Fiat M13/40", 146, 4], [null, 93, 3],
  ]);
  assert.equal(total(e.vliegtuigen), 536);
  assert.deepEqual(lost(e), [52100, 340, 332]);
});

test("Second Battle of El Alamein figures", () => {
  const e = FIGURES["Second Battle of El Alamein"];
  assert.equal(total(e.tanks), 547);
  assert.equal(total(e.vliegtuigen), 835);
  assert.deepEqual(lost(e), [57400, 500, 84]);
});

test("losses and strengths of the other battles", () => {
  const battleaxe = FIGURES["Operation Battleaxe"];
  assert.deepEqual(battleaxe.tanks.map((l) => l.aantal), [100, 96]);
  assert.deepEqual(battleaxe.vliegtuigen.map((l) => l.aantal), [130, 84]);
  assert.deepEqual(lost(battleaxe), [1270, 12, 10]);
  const gazala = FIGURES["Battle of Gazala"];
  assert.equal(gazala.soldaten, 90000);
  assert.equal(total(gazala.tanks), 560);
  assert.equal(total(gazala.vliegtuigen), 542);
  assert.deepEqual(lost(gazala), [6360, 125, 0]);
  assert.deepEqual(lost(FIGURES["Battle of Medenine"]), [635, 47, 0]);
  assert.deepEqual(lost(FIGURES["Battle of Alam el Halfa"]), [2900, 49, 36]);
});

test("Siege of Tobruk has no aircraft strength line, its aircraft are losses", () => {
  const e = FIGURES["Siege of Tobruk"];
  assert.deepEqual(e.vliegtuigen, []);
  assert.equal(lost(e)[2], 112);
});

test("every loss line has a count and a crew", () => {
  for (const [title, entry] of Object.entries(FIGURES)) {
    if (!entry.verliezen) continue;
    for (const line of [...entry.verliezen.tanks, ...entry.verliezen.vliegtuigen]) {
      assert.ok(line.aantal > 0, `${title} loss count`);
      assert.ok(Number.isInteger(line.bemanning) && line.bemanning > 0, `${title} loss crew`);
      assert.ok(line.bron, `${title} loss source`);
    }
  }
});

// Bernard Montgomery: the second test of the same rules.
const MONTY = read("../battles/manschappen.json")["Bernard Montgomery"];
const MONTY_STEPS = [
  "Slag om Leuven (1940)", "Second Battle of El Alamein", "Battle of Alam el Halfa", "Battle of El Agheila",
  "Battle of Tripoli (1943)", "Battle of the Mareth Line", "Battle of Medenine", "Battle of Wadi Akarit",
  "Battle of Enfidaville", "Operation Vulcan", "Operation Strike", "Operation Turkey Buzzard",
  "Allied invasion of Sicily", "Operation Baytown", "Barbara Line", "Moro River campaign",
  "Lądowanie w Normandii", "Pointe du Hoc", "Operation Perch", "Operation Epsom", "Operation Goodwood",
  "Operation Cobra", "Falaise pocket", "Liberation of Paris", "Operation Market Garden", "Operation Fusilade",
  "Battle of the Scheldt", "Battle of St. Vith", "Battle of the Nijmegen salient", "Operation Veritable",
  "Operation Plunder", "Ruhr pocket",
];
const MONTY_OWN = {
  "Second Battle of El Alamein": 195000, "Battle of the Mareth Line": 90000, "Allied invasion of Sicily": 160000,
  "Pointe du Hoc": 225, "Operation Epsom": 60000, "Operation Goodwood": 139000, "Falaise pocket": 580000,
  "Operation Market Garden": 84876, "Battle of the Scheldt": 450000, "Battle of St. Vith": 22000,
  "Operation Veritable": 200000, "Operation Plunder": 1284712,
};
const MONTY_DOTTED = [
  "Slag om Leuven (1940)", "Battle of Alam el Halfa", "Battle of El Agheila", "Battle of Tripoli (1943)",
  "Battle of Medenine", "Battle of Wadi Akarit", "Battle of Enfidaville", "Operation Vulcan", "Operation Strike",
  "Operation Turkey Buzzard", "Barbara Line", "Moro River campaign", "Lądowanie w Normandii", "Operation Perch",
  "Operation Cobra", "Liberation of Paris", "Operation Fusilade", "Battle of the Nijmegen salient", "Ruhr pocket",
];

test("Montgomery: every step of his Spoor is in the file and names a real Veldslag", () => {
  const known = new Set(BATTLES.map((b) => b.title));
  assert.equal(MONTY_STEPS.length, 32);
  for (const title of [...MONTY_STEPS, "Allied invasion of Italy"]) {
    assert.ok(MONTY[title], `${title} missing from manschappen.json`);
    assert.ok(known.has(title), `${title} is not in battles.json`);
  }
  assert.equal(Object.keys(MONTY).length, 33);
});

test("Montgomery: own figures are as in the infobox", () => {
  for (const [title, soldiers] of Object.entries(MONTY_OWN)) {
    assert.equal(MONTY[title].soldaten, soldiers, title);
    assert.equal(MONTY[title].overgenomen_van, null, title);
  }
});

test("Montgomery: only Baytown borrows, only from Allied invasion of Italy", () => {
  for (const [title, entry] of Object.entries(MONTY)) {
    assert.equal(entry.overgenomen_van, title === "Operation Baytown" ? "Allied invasion of Italy" : null, title);
  }
  assert.equal(MONTY["Operation Baytown"].soldaten, null);
  assert.equal(MONTY["Allied invasion of Italy"].soldaten, 189000);
});

test("Montgomery: dotted battles have no soldiers and do not borrow", () => {
  assert.equal(MONTY_DOTTED.length, 19);
  for (const title of MONTY_DOTTED) {
    assert.equal(MONTY[title].soldaten, null, title);
    assert.equal(MONTY[title].overgenomen_van, null, title);
  }
});

test("Montgomery: shape and crews of every entry", () => {
  for (const [title, entry] of Object.entries(MONTY)) {
    assert.ok([1, 2].includes(entry.kolom), title);
    assert.ok(entry.tekst && entry.tekst.length > 0, title);
    assert.doesNotMatch(entry.tekst, /<ref|\{\{|\}\}|<br/, title);
    assert.ok(entry.bron, title);
    for (const line of [...entry.tanks, ...entry.vliegtuigen, ...(entry.verliezen?.tanks ?? []), ...(entry.verliezen?.vliegtuigen ?? [])]) {
      assert.ok(Number.isInteger(line.bemanning) && line.bemanning > 0, title);
      assert.ok(line.aantal > 0 && line.bron, title);
      if (line.type === null) assert.equal(line.bemanning, 3, title);
    }
  }
});

test("Montgomery: Second Battle of El Alamein figures", () => {
  const e = MONTY["Second Battle of El Alamein"];
  assert.equal(e.kolom, 1);
  assert.equal(total(e.tanks), 1029);
  assert.deepEqual(split(e.tanks), [
    ["M3 Grant", 170, 6], ["M4 Sherman", 252, 5], ["Crusader II", 216, 4], ["Crusader III", 78, 3],
    ["M3 Stuart", 119, 4], ["Valentine", 194, 3],
  ]);
  assert.equal(total(e.vliegtuigen), 740);
  assert.deepEqual(lost(e), [13560, 416, 97]);
});

test("Montgomery: Goodwood, Epsom, Market Garden and Plunder", () => {
  const goodwood = MONTY["Operation Goodwood"];
  assert.equal(total(goodwood.tanks), 1369);
  assert.deepEqual(lost(goodwood), [4237, 400, 0]);
  const epsom = MONTY["Operation Epsom"];
  assert.equal(total(epsom.tanks), 600);
  assert.deepEqual(lost(epsom), [4000, 150, 0]);
  const garden = MONTY["Operation Market Garden"];
  assert.equal(total(garden.tanks), 800);
  assert.equal(total(garden.vliegtuigen), 3100);
  assert.deepEqual(lost(garden), [16263, 88, 377]);
  assert.deepEqual(lost(MONTY["Operation Plunder"]), [6781, 0, 0]);
  assert.equal(total(MONTY["Operation Plunder"].tanks), 0);
});

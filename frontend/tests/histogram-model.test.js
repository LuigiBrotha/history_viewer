import { test } from "node:test";
import assert from "node:assert/strict";

import { BENAMINGEN, BINS, benamingOf, binIndex, histogram, isRough } from "../js/histogram-model.js";

const battle = (over = {}) => ({ title: "X", start: "1942-01-01", end: "1942-01-01", precision: "day", ...over });

test("the Benaming is the first of the words in the English title", () => {
  assert.equal(benamingOf(battle({ title: "Battle of Kursk" })), "battle");
  assert.equal(benamingOf(battle({ title: "Battles of Rzhev" })), "battle");
  assert.equal(benamingOf(battle({ title: "Aerial warfare during Operation Barbarossa" })), "operation");
  assert.equal(benamingOf(battle({ title: "Siege of Leningrad" })), "siege");
  assert.equal(benamingOf(battle({ title: "Vistula–Oder Offensive" })), "offensive");
  assert.equal(benamingOf(battle({ title: "Western Desert campaign" })), "campaign");
  assert.equal(benamingOf(battle({ title: "Bombing of Rotterdam" })), "raid");
  assert.equal(benamingOf(battle({ title: "Dieppe Raid" })), "raid");
  // Only whole words: "Operational" or "Battleship" are no Benaming.
  assert.equal(benamingOf(battle({ title: "Sinking of the battleship Bismarck" })), "ander");
  assert.equal(benamingOf(battle({ title: "Operational pause" })), "ander");
});

test("a battle in another language counts by its English name, not by a machine translation", () => {
  const ru = { title: "Ржевская битва", lang: "ru", title_en: "Battles of Rzhev" };
  assert.equal(benamingOf(battle({ ...ru, title_source: "wikipedia" })), "battle");
  assert.equal(benamingOf(battle({ ...ru, title_source: "wikidata" })), "battle");
  assert.equal(benamingOf(battle({ title: "Bitwa o Pomorze", lang: "pl", title_en: "Battle of Pomerania", title_source: "vertaald" })), "vertaald");
  assert.equal(benamingOf(battle({ title: "Bitwa nad Bzurą", lang: "pl" })), "vertaald");
  assert.equal(benamingOf(battle({ title: "Battle of Britain", lang: "en" })), "battle");
});

test("the bars run from one day to more than two years", () => {
  assert.deepEqual(BINS.map((bin) => bin.name),
    ["1 dag", "2–3 dagen", "4–7 dagen", "1–4 weken", "1–3 maanden", "3–12 maanden", "1–2 jaar", "> 2 jaar"]);
  assert.deepEqual([1, 2, 3, 4, 7, 8, 30, 31, 91, 92, 365, 366, 730, 731, 5000].map(binIndex),
    [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7]);
});

test("a battle known only by its month or year is rough", () => {
  assert.equal(isRough(battle()), false);
  assert.equal(isRough(battle({ precision: "month" })), true);
  assert.equal(isRough(battle({ precision: "year" })), true);
});

test("the histogram counts each battle once, by bar and Benaming, the rough ones apart", () => {
  const battles = [
    battle({ title: "Battle of A" }),
    battle({ title: "Battle of B", end: "1942-01-03" }),
    battle({ title: "Operation C", end: "1942-01-03", precision: "month" }),
    battle({ title: "Operation D", end: "1942-01-02" }),
    battle({ title: "Bitwa E", lang: "pl", title_en: "Battle E", title_source: "vertaald" }),
  ];
  const bars = histogram(battles);
  assert.equal(bars.length, BINS.length);
  assert.equal(bars[0].total, 2);
  assert.equal(bars[1].total, 3);
  assert.deepEqual(bars[0].segments.map((s) => s.benaming), BENAMINGEN.map((b) => b.key));
  const operation = bars[1].segments.find((s) => s.benaming === "operation");
  // The rough ones come last in the list.
  assert.deepEqual(operation.battles.map((b) => b.title), ["Operation D", "Operation C"]);
  assert.equal(operation.rough, 1);
  assert.equal(bars[0].segments.find((s) => s.benaming === "vertaald").battles.length, 1);
  assert.equal(bars[7].total, 0);
});

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  liberationBattle,
  liberationKamp,
  liberationPlaces,
  liberationStyle,
  liberationTooltip,
  liberationsInPeriod,
  liberationsOnDate,
} from "../js/liberation-model.js";

const kharkov1 = {
  place: "Харьков", title: "Харьков", lang: "ru", country: "Sovjet-Unie", liberated: "1943-02-16", verb: "bevrijd",
  occupied: "1941-10-25", by: "Voronezjfront", operation: "Харьковская операция (1943)", lat: 50, lng: 36.17,
  source: "ru-ussr", name: "Charkiv",
};
const kharkov2 = {
  ...kharkov1, liberated: "1943-08-23", occupied: "1943-03-16", by: "Steppefront",
  operation: "Белгородско-Харьковская стратегическая наступательная операция (1943)",
};
const mesch = {
  place: "Mesch", title: "Mesch", lang: "nl", country: "Nederland", liberated: "1944-09-12", verb: "bevrijd",
  by: "Amerikaanse 30e Infanteriedivisie", lat: 50.76, lng: 5.72, source: "nl", name: "Mesch",
};
const berlin = {
  place: "Берлин", title: "Берлин", lang: "ru", country: "Duitsland", liberated: "1945-05-02", verb: "ingenomen",
  by: "1e Wit-Russische Front", lat: 52.5, lng: 13.4, source: "ru-abroad", name: "Berlijn",
};

function stateOn(places, day) {
  return liberationsOnDate(places, day).map(({ liberation, state }) => [liberation.name, liberation.liberated, state]);
}

test("a Dutch place is occupied from 10 May 1940 until its liberation, then liberated", () => {
  const places = liberationPlaces([mesch]);
  assert.deepEqual(stateOn(places, "1940-05-09"), []);
  assert.deepEqual(stateOn(places, "1940-05-10"), [["Mesch", "1944-09-12", "occupied"]]);
  assert.deepEqual(stateOn(places, "1944-09-11"), [["Mesch", "1944-09-12", "occupied"]]);
  assert.deepEqual(stateOn(places, "1944-09-12"), [["Mesch", "1944-09-12", "liberated"]]);
});

test("each occupied country has its own start; Axis countries are never occupied", () => {
  const at = (country, day) => stateOn(liberationPlaces([{ ...mesch, country }]), day);
  assert.equal(at("Polen", "1939-09-01").length, 1);
  assert.equal(at("Polen", "1939-08-31").length, 0);
  assert.equal(at("Noorwegen", "1940-04-09").length, 1);
  assert.equal(at("Tsjechoslowakije", "1939-03-15").length, 1);
  assert.equal(at("Joegoslavië", "1941-04-06").length, 1);
  assert.deepEqual(stateOn(liberationPlaces([berlin]), "1945-05-01"), []);
  assert.deepEqual(stateOn(liberationPlaces([berlin]), "1945-05-02"), [["Berlijn", "1945-05-02", "liberated"]]);
});

test("a Soviet town occupied twice is occupied again between its two liberations", () => {
  const places = liberationPlaces([kharkov2, kharkov1]);
  assert.deepEqual(stateOn(places, "1941-10-24"), []);
  assert.deepEqual(stateOn(places, "1941-10-25"), [["Charkiv", "1943-02-16", "occupied"]]);
  assert.deepEqual(stateOn(places, "1943-02-16"), [["Charkiv", "1943-02-16", "liberated"]]);
  assert.deepEqual(stateOn(places, "1943-03-16"), [["Charkiv", "1943-08-23", "occupied"]]);
  assert.deepEqual(stateOn(places, "1943-08-23"), [["Charkiv", "1943-08-23", "liberated"]]);
});

test("a place listed twice without a new occupation stays liberated from its first date", () => {
  const places = liberationPlaces([{ ...mesch, liberated: "1944-09-16" }, mesch]);
  assert.deepEqual(stateOn(places, "1944-09-13"), [["Mesch", "1944-09-12", "liberated"]]);
  assert.deepEqual(stateOn(places, "1944-09-16"), [["Mesch", "1944-09-16", "liberated"]]);
});

test("one place keeps one key over the dates, so its marker is updated, not doubled", () => {
  const places = liberationPlaces([kharkov1, kharkov2, mesch]);
  const keys = (day) => liberationsOnDate(places, day).map(({ key }) => key);
  assert.equal(new Set(keys("1943-02-20")).size, 2);
  assert.deepEqual(keys("1943-02-20"), keys("1943-04-01"));
});

test("Alle routes shows the liberations within the period, and the places still occupied at its end", () => {
  const all = [kharkov1, kharkov2, mesch];
  const names = (from, to) => liberationsInPeriod(all, from, to).map(({ liberation, state }) => [liberation.name, liberation.liberated, state]);
  // Mesch is occupied at the end of 1943; Kharkov was liberated twice within it.
  assert.deepEqual(names("1943-01-01", "1943-12-31"), [
    ["Charkiv", "1943-02-16", "liberated"], ["Charkiv", "1943-08-23", "liberated"], ["Mesch", "1944-09-12", "occupied"],
  ]);
  // In spring 1943 Kharkov is liberated and taken again: occupied at the end.
  assert.deepEqual(names("1943-02-01", "1943-04-30"), [
    ["Charkiv", "1943-02-16", "liberated"], ["Charkiv", "1943-08-23", "occupied"], ["Mesch", "1944-09-12", "occupied"],
  ]);
  // Occupied since before the period counts too, as the atlas shows the end of the period.
  assert.deepEqual(names("1942-01-01", "1942-12-31"), [["Charkiv", "1943-02-16", "occupied"], ["Mesch", "1944-09-12", "occupied"]]);
  assert.deepEqual(names("1944-01-01", null), [["Mesch", "1944-09-12", "liberated"]]);
  assert.deepEqual(names("1939-01-01", "1940-05-09"), []);
  // An Axis town is never occupied, only taken.
  assert.deepEqual(liberationsInPeriod([berlin], "1944-01-01", "1944-12-31"), []);
  assert.equal(names(null, null).length, 3);
  const keys = liberationsInPeriod(all, "1943-02-01", "1943-04-30").map(({ key }) => key);
  assert.equal(new Set(keys).size, keys.length);
});

test("a place without its own occupation date says since when its country was occupied", () => {
  const [onDate] = liberationsOnDate(liberationPlaces([mesch]), "1942-01-01");
  assert.match(liberationTooltip(onDate.liberation), /^Mesch — bezet sinds 10 mei 1940 — bevrijd op 12 september 1944/);
  const [inPeriod] = liberationsInPeriod([mesch], "1942-01-01", "1942-12-31");
  assert.match(liberationTooltip(inPeriod.liberation), /bezet sinds 10 mei 1940/);
  // A town in an Axis country was never occupied.
  const [taken] = liberationsOnDate(liberationPlaces([berlin]), "1945-06-01");
  assert.doesNotMatch(liberationTooltip(taken.liberation), /bezet/);
});

test("the liberator's Kamp: Dutch list westers, Russian lists sovjet", () => {
  assert.equal(liberationKamp(mesch), "westers");
  assert.equal(liberationKamp(kharkov1), "sovjet");
  assert.equal(liberationKamp(berlin), "sovjet");
  assert.equal(liberationKamp({ ...mesch, source: "fr" }), "westers");
  assert.equal(liberationKamp({ ...mesch, source: "nl-be" }), "westers");
});

test("occupied is filled in the colour of the As, liberated in the colour of its liberator's Kamp", () => {
  const occupied = liberationStyle("occupied", mesch);
  assert.equal(occupied.fill, true);
  assert.equal(occupied.fillOpacity, 1);
  // The colours come from the same custom property as the Veldslag squares.
  assert.match(occupied.className, /\bwin1-as\b/);
  assert.match(occupied.className, /\bliberation-occupied\b/);
  const filled = liberationStyle("liberated", mesch);
  assert.equal(filled.fill, true);
  assert.match(filled.className, /\bwin1-westers\b/);
  assert.match(liberationStyle("liberated", kharkov1).className, /\bwin1-sovjet\b/);
  assert.doesNotMatch(occupied.className, /win1-westers|win1-sovjet/);
});

test("the tooltip says when and by whom, in Dutch", () => {
  assert.equal(liberationTooltip(mesch), "Mesch — bevrijd op 12 september 1944 door Amerikaanse 30e Infanteriedivisie");
  assert.equal(liberationTooltip(berlin), "Berlijn (Берлин) — ingenomen op 2 mei 1945 door 1e Wit-Russische Front");
  assert.equal(
    liberationTooltip(kharkov2),
    "Charkiv (Харьков) — bezet sinds 16 maart 1943 — bevrijd op 23 augustus 1943 door Steppefront",
  );
  assert.equal(
    liberationTooltip({ ...mesch, liberated: "1944-10-28", date_text: "nacht van 28-29 oktober", by: undefined }),
    "Mesch — bevrijd op 28 oktober 1944 (nacht van 28-29 oktober)",
  );
  assert.equal(
    liberationTooltip({ ...kharkov1, partial: true }),
    "Charkiv (Харьков) — deels bezet sinds 25 oktober 1941 — bevrijd op 16 februari 1943 door Voronezjfront",
  );
  assert.equal(liberationTooltip({ ...mesch, partial: true }), "Mesch — deels bezet — bevrijd op 12 september 1944 door Amerikaanse 30e Infanteriedivisie");
});

test("the operation leads to the Veldslag of that Russian article", () => {
  const battles = [
    { title: "Battle of Kharkov", url: "https://en.wikipedia.org/wiki/Third_Battle_of_Kharkov" },
    {
      title: "Харьковская операция (1943)",
      url: "https://ru.wikipedia.org/wiki/%D0%A5%D0%B0%D1%80%D1%8C%D0%BA%D0%BE%D0%B2%D1%81%D0%BA%D0%B0%D1%8F_%D0%BE%D0%BF%D0%B5%D1%80%D0%B0%D1%86%D0%B8%D1%8F_(1943)",
    },
  ];
  assert.equal(liberationBattle(kharkov1, battles), "Харьковская операция (1943)");
  assert.equal(liberationBattle(kharkov2, battles), null);
  assert.equal(liberationBattle(mesch, battles), null);
  assert.equal(liberationBattle(kharkov1, []), null);
});

test("a French liberation leads to the Veldslag of its French article", () => {
  const carentan = { ...mesch, lang: "fr", source: "fr", country: "Frankrijk", operation: "Bataille de Carentan" };
  const battles = [{ title: "Bataille de Carentan", url: "https://fr.wikipedia.org/wiki/Bataille_de_Carentan" }];
  assert.equal(liberationBattle(carentan, battles), "Bataille de Carentan");
  // A Russian title never matches a French article of the same name.
  assert.equal(liberationBattle({ ...carentan, lang: "ru" }, battles), null);
});

test("without a Russian Veldslag, the English article of the same operation leads to it", () => {
  const battles = [
    { title: "Belgorod–Kharkov offensive operation", url: "https://en.wikipedia.org/wiki/Belgorod%E2%80%93Kharkov_offensive_operation" },
  ];
  const withEnglish = { ...kharkov2, operation_en: "Belgorod–Kharkov offensive operation" };
  assert.equal(liberationBattle(withEnglish, battles), "Belgorod–Kharkov offensive operation");
  assert.equal(liberationBattle({ ...mesch, operation_en: "Operation Market Garden" }, battles), null);
  // The same title on the Russian Wikipedia is another article.
  assert.equal(liberationBattle({ ...mesch, operation: "Belgorod–Kharkov offensive operation" }, battles), null);
});

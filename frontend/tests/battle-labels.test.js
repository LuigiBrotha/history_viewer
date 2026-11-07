import { test } from "node:test";
import assert from "node:assert/strict";

import {
  labelKey,
  labelText,
  matchesLabels,
  readLabels,
  searchLabels,
  sortBattles,
  writeLabels,
} from "../js/battle-labels.js";

const battle = (over = {}) => ({
  title: "Battle", start: "1942-01-01", end: "1942-01-10", lat: 1, lng: 2, winner: [], countries: [], ...over,
});

test("each kind of label matches what it says", () => {
  const polish = battle({ countries: ["Polen", "Duitsland"], winner: ["as"] });
  const english = battle({ countries: ["Verenigd Koninkrijk"], winner: ["as", "westers"], own: true });
  const dutch = battle({ lang: "nl", lat: null, lng: null });
  assert.equal(matchesLabels(polish, [{ kind: "land", value: "Polen" }, { kind: "land", value: "Duitsland" }]), true);
  assert.equal(matchesLabels(polish, [{ kind: "land", value: "Polen" }, { kind: "land", value: "Japan" }]), false);
  assert.equal(matchesLabels(polish, [{ kind: "winnaar", value: "as" }]), true);
  assert.equal(matchesLabels(english, [{ kind: "winnaar", value: "as" }]), false);
  assert.equal(matchesLabels(english, [{ kind: "winnaar", value: "onbeslist" }]), true);
  assert.equal(matchesLabels(dutch, [{ kind: "winnaar", value: "onbekend" }]), true);
  assert.equal(matchesLabels(dutch, [{ kind: "taal", value: "nl" }]), true);
  assert.equal(matchesLabels(polish, [{ kind: "taal", value: "en" }]), true);
  assert.equal(matchesLabels(english, [{ kind: "positie", value: "eigen" }]), true);
  assert.equal(matchesLabels(polish, [{ kind: "positie", value: "wikipedia" }]), true);
  assert.equal(matchesLabels(dutch, [{ kind: "positie", value: "wikipedia" }]), false);
  assert.equal(matchesLabels(battle({ countries: undefined, winner: undefined }), [{ kind: "land", value: "Polen" }]), false);
  assert.equal(matchesLabels(polish, []), true);
});

test("labels read as text", () => {
  assert.equal(labelText({ kind: "land", value: "Polen" }), "Land: Polen");
  assert.equal(labelText({ kind: "winnaar", value: "sovjet" }), "Winnaar: Sovjet-Unie");
  assert.equal(labelText({ kind: "winnaar", value: "onbekend" }), "Winnaar: onbekend");
  assert.equal(labelText({ kind: "taal", value: "de" }), "Taal: Duits");
  assert.equal(labelText({ kind: "positie", value: "eigen" }), "Positie: eigen positie");
  assert.equal(labelKey({ kind: "land", value: "Polen" }), "land:Polen");
});

test("labels survive the URL, unknown ones are dropped", () => {
  const labels = [{ kind: "land", value: "Bosnië, oost" }, { kind: "winnaar", value: "as" }, { kind: "taal", value: "pl" }];
  assert.deepEqual(readLabels(writeLabels(labels)), labels);
  assert.equal(writeLabels([]), "");
  assert.deepEqual(readLabels("land:Polen,winnaar:nonsense,taal:xx,iets:anders,positie:eigen"), [
    { kind: "land", value: "Polen" }, { kind: "positie", value: "eigen" },
  ]);
  assert.deepEqual(readLabels(""), []);
  assert.deepEqual(readLabels(null), []);
});

test("searchLabels offers countries of the battles and the fixed labels that match", () => {
  const battles = [battle({ countries: ["Polen", "Duitsland"] }), battle({ countries: ["Portugal"] })];
  const labels = (q) => searchLabels(battles, q).map((r) => r.label);
  assert.deepEqual(labels("pol"), ["Land: Polen"]);
  assert.deepEqual(labels("po"), ["Land: Polen", "Land: Portugal", "Taal: Pools", "Positie: eigen positie",
    "Positie: Wikipedia-positie"]);
  assert.ok(labels("sovjet").includes("Winnaar: Sovjet-Unie"));
  assert.ok(labels("duits").includes("Taal: Duits"));
  assert.ok(labels("duits").includes("Land: Duitsland"));
  assert.ok(labels("onbes").includes("Winnaar: onbeslist"));
  assert.deepEqual(labels("x"), []);
  assert.deepEqual(searchLabels(battles, "pol")[0].item, { kind: "land", value: "Polen" });
});

test("sortBattles orders by date, name or duration", () => {
  const a = battle({ title: "B", start: "1940-01-01", end: "1940-12-31" });
  const b = battle({ title: "a", start: "1941-01-01", end: "1941-01-01" });
  const c = battle({ title: "C", start: "1939-09-01", end: "1939-09-30" });
  const titles = (sort) => sortBattles([a, b, c], sort).map((x) => x.title);
  assert.deepEqual(titles("datum"), ["C", "B", "a"]);
  assert.deepEqual(titles("naam"), ["a", "B", "C"]);
  assert.deepEqual(titles("duur"), ["B", "C", "a"]);
});

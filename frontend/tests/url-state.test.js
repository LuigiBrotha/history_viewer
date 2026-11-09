import { test } from "node:test";
import assert from "node:assert/strict";

import { carriedView, readView, writeView } from "../js/url-state.js";

const FULL = {
  date: "1942-03-14",
  battle: "Second Happy Time",
  boat: "u99",
  map: { lat: 48.5, lng: -20.1, zoom: 5 },
};

test("writes the parameters in a fixed order with readable spaces and commas", () => {
  assert.equal(
    writeView(FULL, "date"),
    "?datum=1942-03-14&veldslag=Second_Happy_Time&boot=u99&kaart=48.5000,-20.1000,5",
  );
});

test("round trips a full view", () => {
  assert.deepEqual(readView(writeView(FULL, "date"), "date"), FULL);
});

test("round trips a period view", () => {
  const view = { from: "1941-01-01", to: "1942-12-31", battle: "Battle of Crete" };
  assert.equal(
    writeView(view, "period"),
    "?van=1941-01-01&tot=1942-12-31&veldslag=Battle_of_Crete",
  );
  assert.deepEqual(readView(writeView(view, "period"), "period"), view);
});

test("an empty view is an empty string", () => {
  assert.equal(writeView({}, "date"), "");
  assert.deepEqual(readView("", "date"), {});
});

test("titles that need escaping survive the round trip", () => {
  for (const battle of [
    'Operation "Weserübung"',
    "Battle of the Bulge (1944–45)",
    "Convoy HX 79 & SC 7",
    "Battle of Crete",
  ]) {
    const search = writeView({ battle }, "date");
    assert.deepEqual(readView(search, "date"), { battle }, search);
  }
});

test("each bad value is dropped on its own and the rest stays", () => {
  const cases = [
    ["kaart=abc", "map"],
    ["kaart=91,0,5", "map"],
    ["kaart=0,181,5", "map"],
    ["kaart=0,0,19", "map"],
    ["kaart=0,0,5.5", "map"],
    ["kaart=0,0", "map"],
    ["datum=1942-02-30", "date"],
    ["datum=1950-1-1", "date"],
    ["boot=U 99", "boat"],
    ["veldslag=", "battle"],
  ];
  for (const [bad, field] of cases) {
    const view = readView(`?${bad}&datum=1942-03-14&veldslag=Crete&boot=u99&kaart=1,2,3`, "date");
    const expected = { date: "1942-03-14", battle: "Crete", boat: "u99", map: { lat: 1, lng: 2, zoom: 3 } };
    // The bad parameter comes first, so URLSearchParams.get returns it.
    delete expected[field];
    assert.deepEqual(view, expected, bad);
  }
  assert.deepEqual(readView("?van=x&tot=1942-01-01", "period"), { to: "1942-01-01" });
});

test("a period view reads van and tot and ignores datum", () => {
  assert.deepEqual(
    readView("?datum=1942-03-14&van=1941-01-01&tot=1941-02-01", "period"),
    { from: "1941-01-01", to: "1941-02-01" },
  );
  assert.deepEqual(readView("?van=1941-01-01&datum=1942-03-14", "date"), { date: "1942-03-14" });
});

test("a leap day is real only in a leap year", () => {
  assert.deepEqual(readView("?datum=1944-02-29", "date"), { date: "1944-02-29" });
  assert.deepEqual(readView("?datum=1943-02-29", "date"), {});
});

test("Alleen zonder positie is zonderpositie=1, last, on both kinds of page", () => {
  assert.equal(
    writeView({ ...FULL, nopos: true }, "date"),
    "?datum=1942-03-14&veldslag=Second_Happy_Time&boot=u99&kaart=48.5000,-20.1000,5&zonderpositie=1",
  );
  assert.deepEqual(readView("?zonderpositie=1", "date"), { nopos: true });
  assert.deepEqual(readView("?van=1941-01-01&zonderpositie=1", "period"), { from: "1941-01-01", nopos: true });
  for (const bad of ["0", "true", "", "2"]) assert.deepEqual(readView(`?zonderpositie=${bad}`, "date"), {});
  assert.equal(writeView({ nopos: false }, "date"), "");
});

test("carriedView keeps only battle, boat, map and Alleen zonder positie", () => {
  assert.deepEqual(carriedView({ ...FULL, from: "1941-01-01", to: "1942-01-01", nopos: true }), {
    battle: "Second Happy Time",
    boat: "u99",
    map: { lat: 48.5, lng: -20.1, zoom: 5 },
    nopos: true,
  });
  assert.deepEqual(carriedView({ date: "1942-03-14" }), {});
});


test("the labels and the sort order are kept and carried, the date sort is the default", () => {
  const view = { battle: "Kursk", filter: "land:Polen,winnaar:as", sort: "naam" };
  assert.equal(writeView(view, "period"), "?veldslag=Kursk&filter=land%3APolen%2Cwinnaar%3Aas&sorteer=naam");
  assert.deepEqual(readView(writeView(view, "period"), "period"), view);
  assert.deepEqual(readView("?sorteer=datum&filter=", "date"), {});
  assert.deepEqual(readView("?sorteer=onzin", "date"), {});
  assert.deepEqual(carriedView({ date: "1942-01-01", filter: "taal:nl", sort: "duur" }), { filter: "taal:nl", sort: "duur" });
});

test("OF between the labels and 'Toon alle' are kept and carried; EN and off are the defaults", () => {
  const view = { filter: "land:Polen", labelMode: "of", showAll: true };
  assert.equal(writeView(view, "date"), "?filter=land%3APolen&filtermodus=of&alles=1");
  assert.deepEqual(readView("?filter=land%3APolen&filtermodus=of&alles=1", "date"), view);
  assert.deepEqual(readView("?filtermodus=en&alles=0", "date"), {});
  assert.deepEqual(readView("?filtermodus=onzin", "date"), {});
  assert.equal(writeView({ labelMode: "en", showAll: false }, "date"), "");
  assert.deepEqual(carriedView({ date: "1942-01-01", labelMode: "of", showAll: true }), { labelMode: "of", showAll: true });
});

test("the Spreiding range is kept and carried as spreiding=min-max, the full range is left out", () => {
  assert.equal(writeView({ spread: "20-150" }, "date"), "?spreiding=20-150");
  assert.deepEqual(readView("?spreiding=20-", "date"), { spread: "20-" });
  assert.deepEqual(readView("?spreiding=x", "date"), {});
  assert.deepEqual(carriedView({ date: "1942-01-01", spread: "0-100" }), { spread: "0-100" });
});


test("the Dutch version of the Artikel is kept as artikel=nl, the original is left out", () => {
  assert.equal(writeView({ version: "nl" }, "date"), "?artikel=nl");
  assert.equal(writeView({ version: "origineel" }, "date"), "");
  assert.deepEqual(readView("?artikel=nl", "date"), { version: "nl" });
  assert.deepEqual(readView("?artikel=xx", "date"), {});
  assert.deepEqual(carriedView({ version: "nl", date: "1940-01-01" }), { version: "nl" });
});

test("routes that are switched off stay off in the URL and in links to other pages", () => {
  assert.equal(writeView({ routesOff: true }, "date"), "?routes=uit");
  assert.deepEqual(readView("?routes=uit", "period"), { routesOff: true });
  assert.deepEqual(carriedView({ routesOff: true, date: "1942-01-01" }), { routesOff: true });
  assert.equal(writeView({ routesOff: false }, "date"), "");
  assert.equal(writeView({ ship: "408" }, "date"), "?schip=408");
  assert.deepEqual(readView("?schip=408", "period"), { ship: "408" });
  assert.deepEqual(readView("?schip=%3Cx%3E", "period"), {});
  assert.deepEqual(carriedView({ ship: "408", date: "1942-01-01" }), { ship: "408" });
  assert.equal(writeView({ shipsOff: true }, "date"), "?schepen=uit");
  assert.deepEqual(readView("?schepen=uit", "period"), { shipsOff: true });
  assert.deepEqual(carriedView({ shipsOff: true, date: "1942-01-01" }), { shipsOff: true });
  assert.equal(writeView({ namesOff: true }, "date"), "?namen=uit");
  assert.deepEqual(readView("?namen=uit", "period"), { namesOff: true });
  assert.deepEqual(carriedView({ namesOff: true, date: "1942-01-01" }), { namesOff: true });
  assert.equal(writeView({ boatsOff: true }, "date"), "?boten=uit");
  assert.deepEqual(readView("?boten=uit", "date"), { boatsOff: true });
  assert.deepEqual(carriedView({ boatsOff: true, date: "1942-01-01" }), { boatsOff: true });
  for (const bad of ["aan", "1", ""]) assert.deepEqual(readView(`?routes=${bad}`, "date"), {});
});

test("the width of the band can be read from and written to the URL", () => {
  assert.equal(writeView({ bandWidth: 64 }, "date"), "?banddikte=64");
  assert.deepEqual(readView("?banddikte=64", "date"), { bandWidth: 64 });
  assert.deepEqual(carriedView({ date: "1942-01-01", bandWidth: 64 }), { bandWidth: 64 });
});

test("a width outside the slider is ignored", () => {
  for (const value of ["0", "9999", "abc"]) assert.deepEqual(readView(`?banddikte=${value}`, "date"), {});
});

test("the default width stays out of the URL", () => {
  assert.equal(writeView({ bandWidth: 48 }, "date"), "");
  assert.equal(writeView({}, "date"), "");
});

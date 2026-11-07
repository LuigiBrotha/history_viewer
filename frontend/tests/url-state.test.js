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

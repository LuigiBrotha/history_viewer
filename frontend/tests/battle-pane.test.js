import { test } from "node:test";
import assert from "node:assert/strict";

import { createBattlePane } from "../js/battle-pane.js";
import { Element, installDom } from "./battle-dom.js";
import { TRACK_COLORS } from "../js/track-layer.js";

const battle = (over = {}) => ({
  title: "Battle of Kursk",
  url: "https://en.wikipedia.org/wiki/Battle_of_Kursk",
  start: "1943-07-05",
  end: "1943-08-23",
  precision: "day",
  date_text: "5 July 1943 – 23 August 1943",
  lat: 51.7,
  lng: 36.1,
  part_of: "the Eastern Front of World War II",
  place: "Kursk, Soviet Union",
  ...over,
});

const LIST = [
  battle(),
  battle({ title: "Atlantic", url: "https://en.wikipedia.org/wiki/Battle_of_the_Atlantic", start: "1939-09-03", end: "1945-05-08", date_text: "3 September 1939 – 8 May 1945", lat: null, lng: null, place: "Atlantic Ocean", part_of: "the Second World War" }),
  battle({ title: "Midway", url: "https://en.wikipedia.org/wiki/Battle_of_Midway", start: "1942-06-04", end: "1942-06-07", date_text: "4–7 June 1942", place: "Midway Atoll", part_of: "the Pacific War" }),
];

function setup(mode = "date", battles = LIST) {
  installDom();
  const rootEl = new Element("aside");
  const selected = [];
  const pane = createBattlePane({ rootEl, mode, onSelect: (b) => selected.push(b) });
  pane.setBattles(battles);
  const rows = () => rootEl.byClass("battle-row");
  const titleOf = (row) => row.byClass("battle-row-title")[0].textContent;
  return { pane, rootEl, selected, rows, titleOf };
}

test("the heading counts the battles and the rows go oldest first", () => {
  const { rootEl, rows, titleOf } = setup();
  assert.equal(rootEl.byClass("battle-pane-title")[0].textContent, "Veldslagen (3)");
  assert.deepEqual(rows().map(titleOf), ["Atlantic", "Midway", "Battle of Kursk"]);
});

test("a row shows the dates, the duration and a bar on the shared axis", () => {
  const { rows } = setup();
  const midway = rows()[1];
  assert.equal(midway.byClass("battle-row-dates")[0].textContent, "4–7 June 1942");
  assert.equal(midway.byClass("battle-row-duration")[0].textContent, "4 dagen");
  const bar = midway.byClass("battle-bar")[0];
  assert.match(bar.styleProps["--left"], /^\d+(\.\d+)?%$/);
  assert.match(bar.styleProps["--width"], /^\d+(\.\d+)?%$/);
});

test("the axis names the years", () => {
  const { rootEl } = setup();
  assert.deepEqual(rootEl.byClass("battle-year").map((y) => y.textContent), ["1939", "1940", "1941", "1942", "1943", "1944", "1945"]);
});

test("a battle without a position says so, one with a position does not", () => {
  const { rows } = setup();
  assert.equal(rows()[0].byClass("battle-nopos")[0].textContent, "geen positie");
  assert.equal(rows()[1].byClass("battle-nopos").length, 0);
});

test("the Wikipedia link opens in a new tab without giving the page access", () => {
  const { rows } = setup();
  const link = rows()[2].byClass("battle-row-link")[0];
  assert.equal(link.textContent, "Wikipedia");
  assert.equal(link.getAttribute("href"), "https://en.wikipedia.org/wiki/Battle_of_Kursk");
  assert.equal(link.getAttribute("target"), "_blank");
  assert.match(link.getAttribute("rel"), /noopener/);
});

test("a url that is not Wikipedia gets no link", () => {
  const { rows } = setup("date", [battle({ url: "javascript:alert(1)" })]);
  assert.equal(rows()[0].byClass("battle-row-link").length, 0);
});

test("source text only becomes text", () => {
  const { rows } = setup("date", [battle({ title: "<img src=x onerror=alert(1)>", date_text: "<b>x</b>" })]);
  assert.equal(rows()[0].byClass("battle-row-title")[0].textContent, "<img src=x onerror=alert(1)>");
  assert.equal(rows()[0].byClass("battle-row-dates")[0].textContent, "<b>x</b>");
});

test("the footer names the source", () => {
  const { rootEl } = setup();
  assert.equal(rootEl.byClass("battle-source")[0].textContent, "Bron: Engelse Wikipedia, CC BY-SA 4.0");
});

test("the search hides rows that do not match and counts the rest", () => {
  const { rootEl, rows } = setup();
  const search = rootEl.byClass("battle-search")[0];
  assert.equal(search.tag, "input");
  assert.equal(search.getAttribute("type"), "search");
  search.value = "ATOLL";
  search.dispatch("input");
  assert.deepEqual(rows().map((r) => r.hidden), [true, false, true]);
  assert.equal(rootEl.byClass("battle-pane-title")[0].textContent, "Veldslagen (1)");
  search.value = "zzz";
  search.dispatch("input");
  assert.equal(rootEl.byClass("battle-empty")[0].hidden, false);
  search.value = "";
  search.dispatch("input");
  assert.equal(rootEl.byClass("battle-empty")[0].hidden, true);
  assert.ok(rows().every((r) => !r.hidden));
});

test("on a date the active battles are highlighted and the others stay as they are", () => {
  const { pane, rows } = setup("date");
  pane.setSelection({ date: "1942-06-05" });
  assert.deepEqual(rows().map((r) => [r.classes.has("active"), r.classes.has("dimmed")]), [
    [true, false],
    [true, false],
    [false, false],
  ]);
  pane.setSelection({ date: "1943-07-05" });
  assert.deepEqual(rows().map((r) => r.classes.has("active")), [true, false, true]);
});

test("the selected date is a line on the axis", () => {
  const { pane, rootEl } = setup("date");
  pane.setSelection({ date: "1942-09-01" });
  const line = rootEl.byClass("battle-marker")[0];
  assert.equal(line.hidden, false);
  assert.ok(Math.abs(Number(line.styleProps["--pos"]) - 0.5) < 0.01);
});

test("a period highlights the battles that overlap it and dims the rest, without removing any", () => {
  const { pane, rows } = setup("period");
  pane.setSelection({ from: "1942-06-07", to: "1942-12-31" });
  assert.deepEqual(rows().map((r) => [r.classes.has("active"), r.classes.has("dimmed"), r.hidden]), [
    [true, false, false],
    [true, false, false],
    [false, true, false],
  ]);
});

test("the selected period is a shaded band, and an open period dims nothing", () => {
  const { pane, rootEl, rows } = setup("period");
  pane.setSelection({ from: "1942-09-01", to: null });
  const band = rootEl.byClass("battle-band")[0];
  assert.equal(band.hidden, false);
  assert.ok(Math.abs(Number(band.styleProps["--from"]) - 0.5) < 0.01);
  assert.equal(band.styleProps["--to"], "1");
  pane.setSelection({ from: null, to: null });
  assert.ok(rows().every((r) => !r.classes.has("active") && !r.classes.has("dimmed")));
});

test("changing the selection updates classes and builds no new elements", () => {
  const many = Array.from({ length: 3000 }, (_, i) => battle({ title: `b${i}`, start: "1941-01-01", end: "1941-02-01" }));
  const { pane, rows } = setup("date", many);
  const before = rows().slice();
  let created = 0;
  const original = globalThis.document.createElement;
  globalThis.document.createElement = (tag) => {
    created += 1;
    return original(tag);
  };
  for (let day = 1; day <= 28; day++) {
    pane.setSelection({ date: `1941-01-${String(day).padStart(2, "0")}` });
  }
  pane.setSelection({ date: "1942-01-01" });
  globalThis.document.createElement = original;
  assert.equal(created, 0);
  assert.deepEqual(rows(), before);
  assert.ok(rows().every((r) => !r.classes.has("active")));
});

test("a click on a row reports the battle, a click on the Wikipedia link does not", () => {
  const { rows, selected } = setup();
  rows()[1].byClass("battle-row-meta")[0].dispatch("click");
  assert.deepEqual(selected.map((b) => b.title), ["Midway"]);
  rows()[2].byClass("battle-row-link")[0].dispatch("click");
  rows()[0].byClass("battle-row-title")[0].dispatch("click");
  assert.deepEqual(selected.map((b) => b.title), ["Midway", "Atlantic"]);
});

test("reveal scrolls to the row and marks it, undoing the mark of the previous one", () => {
  const { pane, rows } = setup();
  pane.reveal(LIST[2]);
  assert.equal(rows()[1].classes.has("selected"), true);
  assert.equal(rows()[1].scrolled, 1);
  pane.reveal(LIST[0]);
  assert.equal(rows()[1].classes.has("selected"), false);
  assert.equal(rows()[2].classes.has("selected"), true);
});

test("reveal clears a search that hides the row", () => {
  const { pane, rootEl, rows } = setup();
  const search = rootEl.byClass("battle-search")[0];
  search.value = "atlantic";
  search.dispatch("input");
  pane.reveal(LIST[2]);
  assert.equal(search.value, "");
  assert.equal(rows()[1].hidden, false);
});

test("a selection given before the battles arrive is applied to them", () => {
  installDom();
  const rootEl = new Element("aside");
  const pane = createBattlePane({ rootEl, mode: "date", onSelect() {} });
  pane.setSelection({ date: "1942-06-05" });
  pane.setBattles(LIST);
  assert.deepEqual(rootEl.byClass("battle-row").map((r) => r.classes.has("active")), [true, true, false]);
});

test("when the battles cannot be loaded the pane says so", () => {
  installDom();
  const rootEl = new Element("aside");
  const pane = createBattlePane({ rootEl, mode: "date", onSelect() {} });
  pane.showError();
  assert.match(rootEl.allText(), /Veldslagen konden niet worden geladen\./);
  assert.equal(rootEl.byClass("battle-row").length, 0);
});

function editSetup(battles = LIST) {
  installDom();
  const rootEl = new Element("aside");
  const calls = [];
  const pane = createBattlePane({ rootEl, mode: "date", onEdit: (b) => calls.push(["edit", b.title]), onClear: (b) => calls.push(["clear", b.title]) });
  pane.setBattles(battles);
  const rows = () => rootEl.byClass("battle-row");
  const titleOf = (row) => row.byClass("battle-row-title")[0].textContent;
  const rowOf = (title) => rows().find((r) => titleOf(r) === title);
  return { pane, rootEl, calls, rowOf };
}

test("the edit buttons show only when editable and only on the selected row", () => {
  const { pane, rootEl, rowOf, calls } = editSetup();
  pane.reveal(rowOf("Midway").battle ?? LIST[2]);
  assert.equal(rootEl.byClass("battle-row-edit").length, 0);
  pane.setEditable(true);
  assert.equal(rootEl.byClass("battle-row-edit").length, 1);
  assert.equal(rowOf("Midway").byClass("battle-row-edit")[0].textContent, "Positie aanpassen");
  assert.equal(rowOf("Midway").byClass("battle-row-clear").length, 0);
  rowOf("Midway").byClass("battle-row-edit")[0].dispatch("click");
  assert.deepEqual(calls, [["edit", "Midway"]]);
  pane.reveal(LIST[0]);
  assert.equal(rowOf("Midway").byClass("battle-row-edit").length, 0);
  assert.equal(rowOf("Battle of Kursk").byClass("battle-row-edit").length, 1);
  pane.setEditable(false);
  assert.equal(rootEl.byClass("battle-row-edit").length, 0);
});

test("an own battle shows its label and can have its position cleared; a click on a button does not select", () => {
  const own = battle({ title: "Midway", own: true });
  const selected = [];
  installDom();
  const rootEl = new Element("aside");
  const calls = [];
  const pane = createBattlePane({ rootEl, mode: "date", onSelect: (b) => selected.push(b), onClear: (b) => calls.push(b.title) });
  pane.setBattles([own]);
  pane.setEditable(true);
  pane.reveal(own);
  const row = rootEl.byClass("battle-row")[0];
  assert.equal(row.byClass("battle-ownpos")[0].textContent, "eigen positie");
  assert.equal(row.byClass("battle-nopos").length, 0);
  const clear = row.byClass("battle-row-clear")[0];
  assert.equal(clear.textContent, "Eigen positie wissen");
  clear.dispatch("click");
  assert.deepEqual(calls, ["Midway"]);
  assert.deepEqual(selected, []);
});

const NOPOS = [
  battle({ title: "Placed", lat: 1, lng: 2, start: "1942-01-01", end: "1942-12-31" }),
  battle({ title: "Lost early", lat: null, lng: null, start: "1940-01-01", end: "1940-02-01" }),
  battle({ title: "Lost 1942", lat: null, lng: null, start: "1942-03-01", end: "1942-04-01" }),
];

function nopos(mode = "date") {
  const ctx = setup(mode, NOPOS);
  const box = ctx.rootEl.byClass("battle-nopos-filter")[0];
  const label = ctx.rootEl.byClass("battle-nopos-text")[0];
  const tick = (on) => {
    box.checked = on;
    box.dispatch("change");
  };
  const shown = () => ctx.rows().filter((r) => !r.hidden).map(ctx.titleOf);
  return { ...ctx, box, label, tick, shown };
}

test("the checkbox counts battles without a position under the date, also while unticked", () => {
  const { pane, box, label, tick, shown } = nopos("date");
  assert.equal(box.tag, "input");
  assert.equal(box.getAttribute("type"), "checkbox");
  assert.equal(label.textContent, "Alleen zonder positie (2)");
  pane.setSelection({ date: "1942-03-15" });
  assert.equal(label.textContent, "Alleen zonder positie (1)");
  assert.equal(shown().length, 3);
  tick(true);
  assert.deepEqual(shown(), ["Lost 1942"]);
});

test("ticking hides positioned and inactive rows, and a new date updates the shown rows", () => {
  const { pane, rootEl, box, tick, shown } = nopos("date");
  pane.setSelection({ date: "1940-01-15" });
  tick(true);
  assert.deepEqual(shown(), ["Lost early"]);
  assert.equal(rootEl.byClass("battle-pane-title")[0].textContent, "Veldslagen (1)");
  pane.setSelection({ date: "1942-03-15" });
  assert.deepEqual(shown(), ["Lost 1942"]);
  pane.setSelection({ date: "1943-01-01" });
  assert.deepEqual(shown(), []);
  assert.equal(rootEl.byClass("battle-empty")[0].hidden, false);
  tick(false);
  assert.equal(shown().length, 3);
  assert.equal(box.checked, false);
});

test("in period mode the filter follows the period, and the search text counts", () => {
  const { pane, rootEl, label, tick, shown } = nopos("period");
  pane.setSelection({ from: "1942-01-01", to: "1942-12-31" });
  tick(true);
  assert.deepEqual(shown(), ["Lost 1942"]);
  pane.setSelection({ from: null, to: null });
  assert.deepEqual(shown(), ["Lost early", "Lost 1942"]);
  const search = rootEl.byClass("battle-search")[0];
  search.value = "early";
  search.dispatch("input");
  assert.deepEqual(shown(), ["Lost early"]);
  assert.equal(label.textContent, "Alleen zonder positie (1)");
});

test("reveal of a row the filter hides keeps the box ticked and shows only that extra row", () => {
  const { pane, box, tick, shown } = nopos("period");
  pane.setSelection({ from: null, to: null });
  tick(true);
  pane.reveal(NOPOS[0]);
  assert.equal(box.checked, true);
  assert.deepEqual(shown(), ["Lost early", "Placed", "Lost 1942"]);
  pane.reveal(NOPOS[1]);
  assert.deepEqual(shown(), ["Lost early", "Lost 1942"]);
});

test("a saved Eigen positie keeps the box ticked and the battle listed until another is chosen", () => {
  const { pane, label, box, tick, shown } = nopos("period");
  pane.setSelection({ from: null, to: null });
  tick(true);
  pane.reveal(NOPOS[2]);
  const placed = { ...NOPOS[2], lat: 3, lng: 4, own: true };
  pane.setBattles([NOPOS[0], NOPOS[1], placed]);
  pane.reveal(placed);
  assert.equal(box.checked, true);
  assert.deepEqual(shown(), ["Lost early", "Lost 1942"]);
  assert.equal(label.textContent, "Alleen zonder positie (1)");
  pane.reveal(NOPOS[1]);
  assert.deepEqual(shown(), ["Lost early"]);
});

test("ticking by hand is reported, setting it from outside ticks and filters without a report", () => {
  installDom();
  const rootEl = new Element("aside");
  const heard = [];
  const pane = createBattlePane({ rootEl, mode: "period", onNoposChange: (on) => heard.push(on) });
  pane.setBattles(NOPOS);
  pane.setSelection({ from: null, to: null });
  const box = rootEl.byClass("battle-nopos-filter")[0];
  pane.setOnlyWithoutPosition(true);
  assert.equal(box.checked, true);
  assert.equal(rootEl.byClass("battle-row").filter((r) => !r.hidden).length, 2);
  assert.deepEqual(heard, []);
  box.checked = false;
  box.dispatch("change");
  box.checked = true;
  box.dispatch("change");
  assert.deepEqual(heard, [false, true]);
});

test("reveal of a row the filter shows keeps the box ticked", () => {
  const { pane, box, tick } = nopos("period");
  pane.setSelection({ from: null, to: null });
  tick(true);
  pane.reveal(NOPOS[1]);
  assert.equal(box.checked, true);
});

test("a battle that gets an Eigen positie drops out of the filtered list", () => {
  const { pane, label, tick, shown } = nopos("period");
  pane.setSelection({ from: null, to: null });
  tick(true);
  pane.setBattles([NOPOS[0], NOPOS[1], { ...NOPOS[2], lat: 3, lng: 4, own: true }]);
  assert.deepEqual(shown(), ["Lost early"]);
  assert.equal(label.textContent, "Alleen zonder positie (1)");
});

test("a battle from another Wikipedia shows its language next to the title", () => {
  const { rows } = setup("date", [battle({ title: "Slag om K", lang: "nl" }), battle({ title: "Kursk" })]);
  const labels = rows().map((r) => r.byClass("battle-lang").map((l) => l.textContent));
  assert.deepEqual(labels.sort(), [[], ["NL"]].sort());
});

test("neighbour walks the visible rows from the selected one, and starts at an end without one", () => {
  const { pane, rootEl } = setup("date", NOPOS);
  assert.equal(pane.neighbour(1).title, "Lost early");
  assert.equal(pane.neighbour(-1).title, "Lost 1942");
  pane.reveal(NOPOS[1]);
  assert.equal(pane.neighbour(1).title, "Placed");
  assert.equal(pane.neighbour(-1), null);
  const search = rootEl.byClass("battle-search")[0];
  search.value = "lost";
  search.dispatch("input");
  pane.reveal(NOPOS[2]);
  assert.equal(pane.neighbour(1), null);
  assert.equal(pane.neighbour(-1).title, "Lost early");
});

test("nextUnplaced finds the next visible battle without a position after the given one", () => {
  const { pane } = setup("date", [
    battle({ title: "A", start: "1940-01-01", lat: null, lng: null }),
    battle({ title: "B", start: "1941-01-01" }),
    battle({ title: "C", start: "1942-01-01", lat: null, lng: null }),
  ]);
  assert.equal(pane.nextUnplaced("A").title, "C");
  assert.equal(pane.nextUnplaced("C"), null);
  assert.equal(pane.nextUnplaced("B").title, "C");
});

const LABELLED = [
  battle({ title: "Bzura", start: "1939-09-09", end: "1939-09-22", countries: ["Polen", "Duitsland"], winner: ["as"] }),
  battle({ title: "Arnhem", start: "1944-09-17", end: "1944-09-25", countries: ["Verenigd Koninkrijk", "Duitsland"], winner: ["as"] }),
  battle({ title: "Kursk", start: "1943-07-05", end: "1943-08-23", countries: ["Duitsland", "Sovjet-Unie"], winner: ["sovjet"] }),
];

function labelled() {
  installDom();
  const rootEl = new Element("aside");
  const removed = [];
  const sorts = [];
  const pane = createBattlePane({ rootEl, mode: "period", onLabelRemove: (l) => removed.push(l), onSortChange: (s) => sorts.push(s) });
  pane.setBattles(LABELLED);
  pane.setSelection({ from: null, to: null });
  const shown = () => rootEl.byClass("battle-list")[0].children.filter((r) => !r.hidden)
    .map((r) => r.byClass("battle-row-title")[0].textContent);
  return { pane, rootEl, removed, sorts, shown };
}

test("labels filter the list, show as removable chips and count", () => {
  const { pane, rootEl, removed, shown } = labelled();
  pane.setLabels([{ kind: "land", value: "Duitsland" }, { kind: "winnaar", value: "as" }]);
  assert.deepEqual(shown(), ["Bzura", "Arnhem"]);
  assert.equal(rootEl.byClass("battle-pane-title")[0].textContent, "Veldslagen (2)");
  const chips = rootEl.byClass("battle-filter");
  // Not the classes of the names beside the squares, whose styles would lay the chip out wrong.
  assert.equal(rootEl.byClass("battle-label").length, 0);
  assert.equal(rootEl.byClass("battle-label-text").length, 0);
  assert.deepEqual(chips.map((c) => c.byClass("battle-filter-text")[0].textContent), ["Land: Duitsland", "Winnaar: As"]);
  chips[1].byClass("battle-filter-remove")[0].dispatch("click");
  assert.deepEqual(removed, [{ kind: "winnaar", value: "as" }]);
  pane.setLabels([]);
  assert.equal(shown().length, 3);
  assert.equal(rootEl.byClass("battle-filter").length, 0);
});

test("the sort choice orders the rows and the arrow keys follow that order", () => {
  const { pane, rootEl, sorts, shown } = labelled();
  assert.deepEqual(shown(), ["Bzura", "Kursk", "Arnhem"]);
  const select = rootEl.byClass("battle-sort")[0];
  select.value = "naam";
  select.dispatch("change");
  assert.deepEqual(sorts, ["naam"]);
  assert.deepEqual(shown(), ["Arnhem", "Bzura", "Kursk"]);
  assert.equal(pane.neighbour(1).title, "Arnhem");
  pane.setSort("duur");
  assert.equal(select.value, "duur");
  assert.deepEqual(shown(), ["Kursk", "Bzura", "Arnhem"]);
});

test("a Spoor chip shows the colour of its line on the map", () => {
  const { pane, rootEl } = labelled();
  pane.setLabels([{ kind: "land", value: "Duitsland" }, { kind: "bevelhebber", value: "Erwin Rommel" }]);
  const [land, rommel] = rootEl.byClass("battle-filter");
  assert.equal(land.byClass("battle-filter-swatch").length, 0);
  assert.equal(rommel.byClass("battle-filter-swatch")[0].style.background, TRACK_COLORS[0]);
});

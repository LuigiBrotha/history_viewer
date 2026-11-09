import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

import { createSubjectList } from "../js/subject-list.js";
import { Element, installDom } from "./battle-dom.js";

beforeEach(installDom);

const ITEMS = [
  { key: "u1", title: "U-1", meta: "IIA", search: "u-1 iia" },
  { key: "u2", title: "U-2", meta: "IIA", search: "u-2 iia" },
  { key: "u3", title: "U-3", meta: "VIIC", search: "u-3 viic" },
];

function setup() {
  const rootEl = new Element("div");
  const picked = [];
  const counts = [];
  const list = createSubjectList({ rootEl, emptyText: "Niets.", onPick: (item) => picked.push(item.key), onCount: (n) => counts.push(n) });
  list.setItems(ITEMS);
  const rows = () => rootEl.byClass("subject-row");
  const row = (key) => rows().find((r) => r.getAttribute("data-key") === key);
  return { rootEl, list, picked, counts, row };
}

test("a click anywhere on a row picks it", () => {
  const { row, picked } = setup();
  row("u2").byClass("subject-row-meta")[0].dispatch("click");
  assert.deepEqual(picked, ["u2"]);
});

test("search hides what does not match, counts the rest and says so when nothing is left", () => {
  const { rootEl, list, row, counts } = setup();
  list.setSearch(" VIIC ");
  assert.equal(row("u1").hidden, true);
  assert.equal(row("u3").hidden, false);
  assert.equal(counts.at(-1), 1);
  list.setSearch("zzz");
  assert.equal(rootEl.byClass("subject-empty")[0].hidden, false);
});

test("the chosen row stays listed through a search, marked and scrolled to", () => {
  const { list, row } = setup();
  list.reveal("u1");
  list.setSearch("viic");
  assert.equal(row("u1").hidden, false);
  assert.equal(row("u1").classes.has("selected"), true);
  assert.equal(row("u1").scrolled, 1);
  list.clear();
  assert.equal(row("u1").hidden, true);
  assert.equal(row("u1").classes.has("selected"), false);
});

test("marks show what is active; with dim the others fade, and null clears them", () => {
  const { list, row } = setup();
  list.setMarks((item) => item.key === "u1", true);
  assert.equal(row("u1").classes.has("active"), true);
  assert.equal(row("u2").classes.has("dimmed"), true);
  list.setMarks(null);
  assert.equal(row("u1").classes.has("active"), false);
  assert.equal(row("u2").classes.has("dimmed"), false);
});

test("new items keep the chosen row and the marks", () => {
  const { list, row } = setup();
  list.reveal("u2");
  list.setMarks((item) => item.key === "u2");
  list.setItems(ITEMS);
  assert.equal(row("u2").classes.has("selected"), true);
  assert.equal(row("u2").classes.has("active"), true);
});

test("rows found in the texts come first, best first, and go back when the search ends", () => {
  const { rootEl, list, row, counts } = setup();
  const keys = () => rootEl.byClass("subject-row").map((r) => r.getAttribute("data-key"));
  list.setSearch("woord");
  list.setHits(["u3", "u1"]);
  assert.deepEqual(keys(), ["u3", "u1", "u2"]);
  assert.equal(row("u1").hidden, false);
  assert.equal(row("u2").hidden, true);
  assert.equal(counts.at(-1), 2);
  list.setHits(null);
  assert.deepEqual(keys(), ["u1", "u2", "u3"]);
});

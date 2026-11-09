import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

import { createSubjectColumn } from "../js/subject-column.js";
import { Element, installDom } from "./battle-dom.js";

beforeEach(installDom);

function memory(initial = {}) {
  const data = { ...initial };
  return { data, getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = value; } };
}

function setup(storage = memory()) {
  const rootEl = new Element("aside");
  let minimized = 0;
  const column = createSubjectColumn({ rootEl, storage, onMinimize: () => { minimized += 1; } });
  const toggles = rootEl.byClass("subject-toggle");
  return { rootEl, column, toggles, storage, minimized: () => minimized };
}

test("the column is Onderwerpen with Veldslagen, U-boten and Schepen, only Veldslagen open", () => {
  const { rootEl, column, toggles } = setup();
  assert.equal(rootEl.byTag("h2")[0].textContent, "Onderwerpen");
  assert.deepEqual(toggles.map((t) => t.getAttribute("aria-expanded")), ["true", "false", "false"]);
  assert.equal(column.sections.battles.bodyEl.hidden, false);
  assert.equal(column.sections.ships.bodyEl.hidden, true);
});

test("each section folds on its own and the choice is remembered", () => {
  const { toggles, column, storage } = setup();
  toggles[1].dispatch("click");
  assert.equal(column.sections.boats.bodyEl.hidden, false);
  assert.equal(column.sections.battles.bodyEl.hidden, false);
  toggles[0].dispatch("click");
  assert.equal(column.sections.battles.bodyEl.hidden, true);
  const again = setup(storage);
  assert.deepEqual(again.toggles.map((t) => t.getAttribute("aria-expanded")), ["false", "true", "false"]);
});

test("the count goes in the head and the one search field reaches every listener", () => {
  const { column } = setup();
  column.setCount("ships", 12);
  assert.equal(column.sections.ships.titleEl.textContent, "Schepen (12)");
  const heard = [];
  column.onSearch((text) => heard.push(text));
  column.search.value = "bis";
  column.search.dispatch("input");
  assert.deepEqual(heard, ["bis"]);
});

test("the minimise button asks the page to fold the column away", () => {
  const { rootEl, minimized } = setup();
  rootEl.byClass("battle-pane-minimize")[0].dispatch("click");
  assert.equal(minimized(), 1);
});

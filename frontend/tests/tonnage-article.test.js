import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

import { createShipArticle } from "../js/tonnage-article.js";
import { Element, installDom } from "./battle-dom.js";

beforeEach(installDom);

const ship = { name: "Empress of Britain", ship_external_id: "1", boat_slug: "u32", boat_number: "U-32", date: "1940-10-28", tons: 42348, outcome: "sunk" };
const other = { ...ship, name: "Magog", ship_external_id: "2" };

function setup() {
  const rootEl = new Element("article");
  const toggles = [];
  const load = { ship: async () => ({ details: null, hits: [], translated: false }), boat: async () => ({ number: "U-32", slug: "u32" }) };
  const article = createShipArticle({ rootEl, getShips: () => [ship, other], onToggle: () => toggles.push(rootEl.hidden), load });
  return { rootEl, article, toggles };
}

test("the panel starts hidden and opens with the name of the ship, reporting that the room changed", async () => {
  const { rootEl, article, toggles } = setup();
  assert.equal(rootEl.hidden, true);
  await article.open(ship);
  assert.equal(rootEl.hidden, false);
  assert.equal(rootEl.byTag("h2")[0].textContent, "Empress of Britain");
  assert.deepEqual(toggles, [false]);
});

test("the next ship replaces the Artikel, without the panel changing size", async () => {
  const { rootEl, article, toggles } = setup();
  await article.open(ship);
  await article.open(other);
  assert.equal(rootEl.byTag("h2")[0].textContent, "Magog");
  assert.deepEqual(toggles, [false]);
});

test("the cross closes the panel, reports it and clears the open ship", async () => {
  const { rootEl, article, toggles } = setup();
  await article.open(ship);
  assert.equal(article.current(), ship);
  rootEl.byClass("article-close")[0].dispatch("click");
  assert.equal(rootEl.hidden, true);
  assert.deepEqual(toggles, [false, true]);
  assert.equal(article.current(), null);
});

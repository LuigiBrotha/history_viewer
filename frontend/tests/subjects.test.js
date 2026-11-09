import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

import { createSubjectColumn } from "../js/subject-column.js";
import { createSubjects } from "../js/subjects.js";
import { Element, installDom } from "./battle-dom.js";

beforeEach(installDom);

const hit = (id, slug, date) => ({ ship_external_id: id, boat_slug: slug, boat_number: slug.toUpperCase(), name: `Ship ${id}`, date, tons: 100, outcome: "sunk" });

const flush = () => new Promise((resolve) => setImmediate(resolve));

async function setup() {
  const storage = { getItem: () => null, setItem() {} };
  const column = createSubjectColumn({ rootEl: new Element("aside"), storage });
  const closed = [];
  const selected = [];
  const battles = { column, onArticleClosed: (f) => closed.push(f), onBattleSelected: (f) => selected.push(f) };
  const writes = {};
  const urlSync = { update: (partial) => Object.assign(writes, partial) };
  const log = [];
  let followedSlug = null;
  const hooks = {
    follow(slug, options) { followedSlug = slug; log.push(["follow", slug, options.fromList]); },
    stopFollow() { followedSlug = null; log.push(["stop"]); },
    followed: () => followedSlug,
    showShip(h, options) { log.push(["showShip", h.boat_slug, options.fromList]); },
  };
  const opened = [];
  const panel = () => ({ open: (slug) => opened.push(["boat", slug]), openShip: (h) => opened.push(["ship", h.ship_external_id, h.boat_slug]) });
  const boats = [{ slug: "u1", number: "U-1", patrol_count: 1 }, { slug: "u2", number: "U-2", patrol_count: 1 }];
  const ships = [hit("9", "u1", "1940-01-01"), hit("9", "u2", "1941-01-01"), hit("8", "u2", "1942-01-01")];
  const subjects = createSubjects({ battles, urlSync, getShips: () => ships, hooks, loadBoats: async () => boats, panel });
  await flush();
  subjects.setShips(ships);
  const rows = (id) => column.sections[id].bodyEl.byClass("subject-row");
  const row = (id, key) => rows(id).find((r) => r.getAttribute("data-key") === key);
  return { subjects, column, writes, log, opened, closed, selected, row, followed: () => followedSlug };
}

test("a boat in the list goes into the Artikel, is followed from the list and is in the URL", async () => {
  const { row, opened, log, writes } = await setup();
  row("boats", "u1").dispatch("click", { target: row("boats", "u1") });
  assert.deepEqual(opened, [["boat", "u1"]]);
  assert.deepEqual(log, [["follow", "u1", true]]);
  assert.deepEqual([writes.boat, writes.ship], ["u1", null]);
  assert.equal(row("boats", "u1").classes.has("selected"), true);
});

test("a boat clicked on the map is not a choice from the list", async () => {
  const { subjects, log } = await setup();
  subjects.openBoat("u1");
  assert.deepEqual(log, [["follow", "u1", false]]);
});

test("a ship of the followed boat keeps the boat followed, and shows that boat's hit", async () => {
  const { subjects, row, opened, log, writes, followed } = await setup();
  subjects.openBoat("u2");
  log.length = 0;
  row("ships", "9").dispatch("click", { target: row("ships", "9") });
  assert.equal(followed(), "u2");
  assert.deepEqual(opened.at(-1), ["ship", "9", "u2"]);
  assert.deepEqual(log, [["showShip", "u2", true]]);
  assert.deepEqual([writes.ship, writes.boat], ["9", "u2"]);
  assert.equal(row("boats", "u2").classes.has("selected"), true);
});

test("a ship of another boat ends the following", async () => {
  const { subjects, opened, log, writes, followed, row } = await setup();
  subjects.openBoat("u1");
  subjects.openShip(hit("8", "u2", "1942-01-01"));
  assert.equal(followed(), null);
  assert.deepEqual(log.at(-2), ["stop"]);
  assert.deepEqual(opened.at(-1), ["ship", "8", "u2"]);
  assert.equal(writes.boat, null);
  assert.equal(row("boats", "u1").classes.has("selected"), false);
});

test("choosing a battle or closing the Artikel ends the following and clears the rows", async () => {
  for (const event of ["selected", "closed"]) {
    const ctx = await setup();
    ctx.subjects.openBoat("u1");
    ctx[event][0]();
    assert.equal(ctx.followed(), null);
    assert.equal(ctx.row("boats", "u1").classes.has("selected"), false);
    assert.deepEqual([ctx.writes.boat, ctx.writes.ship], [null, null]);
  }
});

test("the date marks boats on patrol and ships hit by then", async () => {
  const { subjects, row } = await setup();
  subjects.setDate("1941-06-01", new Set(["u2"]));
  assert.equal(row("boats", "u2").classes.has("active"), true);
  assert.equal(row("boats", "u1").classes.has("active"), false);
  assert.equal(row("ships", "9").classes.has("active"), true);
  assert.equal(row("ships", "8").classes.has("active"), false);
});

test("a period marks and dims; with no period there are no marks", async () => {
  const { subjects, row } = await setup();
  subjects.setRoutes([{ boat_slug: "u1", departure_date: "1940-01-01", arrival_date: "1940-02-01", points: [] }]);
  subjects.setPeriod("1940-01-15", "1940-03-01");
  assert.equal(row("boats", "u1").classes.has("active"), true);
  assert.equal(row("boats", "u2").classes.has("dimmed"), true);
  subjects.setPeriod(null, null);
  assert.equal(row("boats", "u2").classes.has("dimmed"), false);
});

test("a ship from the URL waits for the ships", async () => {
  const { subjects, opened } = await setup();
  subjects.restoreShip("777");
  assert.deepEqual(opened, []);
  subjects.setShips([hit("777", "u1", "1943-01-01")]);
  assert.deepEqual(opened, [["ship", "777", "u1"]]);
});

test("the search reaches both lists and the counts go in the heads", async () => {
  const { column, row } = await setup();
  assert.equal(column.sections.boats.titleEl.textContent, "U-boten (2)");
  column.search.value = "ship 8";
  column.search.dispatch("input");
  assert.equal(column.sections.ships.titleEl.textContent, "Schepen (1)");
  assert.equal(row("ships", "9").hidden, true);
});

import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

import { createArticlePane } from "../js/battle-article.js";
import { Element, installDom } from "./battle-dom.js";

beforeEach(installDom);

const battle = { title: "Battle of the Atlantic", url: "https://en.wikipedia.org/wiki/Battle_of_the_Atlantic" };

function setup(load, extra = {}) {
  const rootEl = new Element("article");
  const calls = { links: [], closed: 0 };
  const pane = createArticlePane({
    rootEl,
    load,
    onBattleLink: (title) => calls.links.push(title),
    onClose: () => (calls.closed += 1),
    ...extra,
  });
  return { rootEl, pane, calls };
}

const deferred = () => {
  let resolve;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
};

test("show titles the pane, loads by title and renders the article with its source", async () => {
  const seen = [];
  const { rootEl, pane } = setup(async (title) => {
    seen.push(title);
    return { title, html: '<a href="/x">Een link</a>', url: battle.url };
  });
  const done = pane.show(battle);
  assert.equal(rootEl.byTag("h2")[0].textContent, "Battle of the Atlantic");
  assert.match(rootEl.allText(), /Laden…/);
  await done;
  assert.deepEqual(seen, ["Battle of the Atlantic"]);
  assert.doesNotMatch(rootEl.allText(), /Laden…/);
  assert.match(rootEl.allText(), /Een link/);
  const source = rootEl.byClass("article-source")[0];
  assert.match(source.allText(), /Bron: Engelse Wikipedia, CC BY-SA 4\.0/);
  const link = source.byTag("a")[0];
  assert.equal(link.getAttribute("href"), battle.url);
  assert.equal(link.getAttribute("target"), "_blank");
  assert.equal(link.getAttribute("rel"), "noopener noreferrer");
});

test("no article gives a message and the Wikipedia link", async () => {
  const { rootEl, pane } = setup(async () => null);
  await pane.show(battle);
  assert.match(rootEl.allText(), /Geen artikel beschikbaar voor deze veldslag\./);
  assert.equal(rootEl.byClass("article-source")[0].byTag("a")[0].getAttribute("href"), battle.url);
});

test("a failed load gives an error message and the Wikipedia link", async () => {
  const { rootEl, pane } = setup(async () => {
    throw new Error("boom");
  });
  await pane.show(battle);
  assert.match(rootEl.allText(), /Artikel kon niet worden geladen\./);
  assert.equal(rootEl.byClass("article-source")[0].byTag("a")[0].getAttribute("href"), battle.url);
});

test("a stale response is dropped when a later show started", async () => {
  const first = deferred();
  const second = deferred();
  const queue = [first, second];
  const { rootEl, pane } = setup(() => queue.shift().promise);
  const a = pane.show({ title: "A", url: "https://en.wikipedia.org/wiki/A" });
  const b = pane.show({ title: "B", url: "https://en.wikipedia.org/wiki/B" });
  second.resolve({ title: "B", html: '<a href="/b">Tekst B</a>', url: "u" });
  await b;
  first.resolve({ title: "A", html: '<a href="/a">Tekst A</a>', url: "u" });
  await a;
  assert.equal(rootEl.byTag("h2")[0].textContent, "B");
  assert.match(rootEl.allText(), /Tekst B/);
  assert.doesNotMatch(rootEl.allText(), /Tekst A/);
});

test("clicking a battle link opens that battle instead of navigating", async () => {
  const html = '<a href="/wiki/Second_Happy_Time" data-battle="Second Happy Time">SHT</a><a href="https://example.org/">Extern</a>';
  const { rootEl, pane, calls } = setup(async () => ({ title: "x", html, url: "u" }));
  await pane.show(battle);
  const [internal, external] = rootEl.byClass("article-body")[0].byTag("a");
  const click = internal.dispatch("click");
  assert.equal(click.defaultPrevented, true);
  assert.deepEqual(calls.links, ["Second Happy Time"]);
  assert.equal(external.getAttribute("target"), "_blank");
  assert.equal(external.getAttribute("rel"), "noopener noreferrer");
  assert.equal(internal.getAttribute("target"), null);
  const other = external.dispatch("click");
  assert.equal(other.defaultPrevented, undefined);
  assert.deepEqual(calls.links, ["Second Happy Time"]);
});

test("the close button calls onClose", () => {
  const { rootEl, calls } = setup(async () => null);
  const close = rootEl.byTag("button")[0];
  assert.equal(close.getAttribute("aria-label"), "Sluit artikel");
  close.dispatch("click");
  assert.equal(calls.closed, 1);
});

test("clear empties the title and body and drops a pending load", async () => {
  const pending = deferred();
  const { rootEl, pane } = setup(() => pending.promise);
  const done = pane.show(battle);
  pane.clear();
  pending.resolve({ title: "x", html: '<a href="/a">Tekst</a>', url: "u" });
  await done;
  assert.equal(rootEl.byTag("h2")[0].textContent, "");
  assert.doesNotMatch(rootEl.allText(), /Tekst|Laden/);
});


test("the Winnaar line names the winning Kamp and is emptied by clear", async () => {
  const { rootEl, pane } = setup(async () => null);
  const line = () => rootEl.byClass("article-winner")[0];
  await pane.show({ title: "Battle of Kursk", url: "https://en.wikipedia.org/wiki/Battle_of_Kursk", winner: ["sovjet"] });
  assert.equal(line().textContent, "Winnaar: Sovjet-Unie");
  assert.equal(line().hidden, false);
  pane.clear();
  assert.equal(line().hidden, true);
});

test("an article in another language is loaded in that language and labelled", async () => {
  const asked = [];
  const { rootEl, pane } = setup(async (title, lang) => {
    asked.push([title, lang]);
    return null;
  });
  await pane.show({ title: "Slag om K", url: "https://nl.wikipedia.org/wiki/Slag_om_K", lang: "nl" });
  await pane.show({ title: "Battle of Kursk", url: "https://en.wikipedia.org/wiki/Battle_of_Kursk" });
  assert.deepEqual(asked, [["Slag om K", "nl"], ["Battle of Kursk", "en"]]);
  assert.equal(rootEl.byClass("article-lang")[0].hidden, true);
});

test("the Plaatshints line shows what it is given, hides when empty and on clear or a new battle", async () => {
  const { rootEl, pane } = setup(async () => null);
  const line = () => rootEl.byClass("article-places")[0];
  await pane.show({ title: "Battle of Kursk", url: "https://en.wikipedia.org/wiki/Battle_of_Kursk" });
  assert.equal(line().hidden, true);
  pane.setPlaceStats("Positie 12 km van het midden van 9 Plaatshints · spreiding 80 km");
  assert.equal(line().textContent, "Positie 12 km van het midden van 9 Plaatshints · spreiding 80 km");
  assert.equal(line().hidden, false);
  pane.setPlaceStats("");
  assert.equal(line().hidden, true);
  pane.setPlaceStats("x");
  await pane.show({ title: "Midway", url: "https://en.wikipedia.org/wiki/Midway" });
  assert.equal(line().hidden, true);
  pane.setPlaceStats("x");
  pane.clear();
  assert.equal(line().hidden, true);
});

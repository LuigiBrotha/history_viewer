import { test, mock } from "node:test";
import assert from "node:assert/strict";

import { createUrlSync } from "../js/url-sync.js";

function fakeLink(href, carry) {
  const attrs = { href, ...(carry ? { "data-carry": carry } : {}) };
  return {
    getAttribute: (name) => attrs[name] ?? null,
    setAttribute: (name, value) => {
      attrs[name] = value;
    },
  };
}

function setup(links = []) {
  const calls = [];
  const win = {
    location: { pathname: "/kaart" },
    history: {
      replaceState: (...args) => calls.push(args),
      pushState: () => {
        throw new Error("pushState must never be used");
      },
    },
  };
  const doc = { querySelectorAll: () => links.filter((l) => l.getAttribute("data-carry")) };
  return { calls, sync: createUrlSync({ kind: "date", win, doc, delayMs: 250 }) };
}

test("ten updates within the delay make one replaceState with the last view", () => {
  mock.timers.enable(["setTimeout"]);
  try {
    const { calls, sync } = setup();
    for (let day = 1; day <= 10; day++) sync.update({ date: `1942-03-${String(day).padStart(2, "0")}` });
    assert.equal(calls.length, 0);
    mock.timers.tick(250);
    assert.deepEqual(calls, [[null, "", "/kaart?datum=1942-03-10"]]);
  } finally {
    mock.timers.reset();
  }
});

test("a null value removes the field", () => {
  mock.timers.enable(["setTimeout"]);
  try {
    const { calls, sync } = setup();
    sync.update({ date: "1942-03-14", battle: "Battle of Crete" });
    mock.timers.tick(250);
    sync.update({ battle: null });
    mock.timers.tick(250);
    assert.equal(calls.at(-1)[2], "/kaart?datum=1942-03-14");
  } finally {
    mock.timers.reset();
  }
});

test("links to other map pages carry the view without the date; other links stay", () => {
  mock.timers.enable(["setTimeout"]);
  try {
    const status = fakeLink("status", "period");
    const chart = fakeLink("grafiek");
    const { sync } = setup([status, chart]);
    sync.update({ date: "1942-03-14", battle: "Battle of Crete", map: { lat: 38, lng: -72, zoom: 6 } });
    mock.timers.tick(250);
    assert.equal(status.getAttribute("href"), "status?veldslag=Battle_of_Crete&kaart=38.0000,-72.0000,6");
    assert.equal(chart.getAttribute("href"), "grafiek");
    sync.update({ battle: null });
    mock.timers.tick(250);
    assert.equal(status.getAttribute("href"), "status?kaart=38.0000,-72.0000,6");
  } finally {
    mock.timers.reset();
  }
});

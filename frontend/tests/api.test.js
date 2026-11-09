import { test } from "node:test";
import assert from "node:assert/strict";

import { canEdit, excludePoint, fetchBoats, fetchRoutes, fetchStatus, restorePoint, fetchBoat, fetchAllRoutes, fetchShip, fetchBattlePositions, saveBattlePosition, clearBattlePosition } from "../js/api.js";

test("fetchBoats calls the boten endpoint and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [{ slug: "u1" }] };
  };

  const result = await fetchBoats();

  assert.deepEqual(calls, ["api/uboats/boten"]);
  assert.deepEqual(result, [{ slug: "u1" }]);
});

test("fetchRoutes calls the routes endpoint and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [{ boat_slug: "u1" }] };
  };

  const result = await fetchRoutes();

  assert.deepEqual(calls, ["api/uboats/routes"]);
  assert.deepEqual(result, [{ boat_slug: "u1" }]);
});

test("fetchBoats rejects when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 500 });

  await assert.rejects(() => fetchBoats(), /Failed to fetch boats: 500/);
});

test("fetchRoutes rejects when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 404 });

  await assert.rejects(() => fetchRoutes(), /Failed to fetch routes: 404/);
});

test("fetchRoutes adds an encoded since parameter", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [] };
  };

  await fetchRoutes("2026-11-04T10:00:00+00:00");

  assert.deepEqual(calls, ["api/uboats/routes?since=2026-11-04T10%3A00%3A00%2B00%3A00"]);
});

test("fetchStatus calls the status endpoint and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => ({ boats_crawled: 3 }) };
  };

  const result = await fetchStatus();

  assert.deepEqual(calls, ["api/uboats/status"]);
  assert.deepEqual(result, { boats_crawled: 3 });
});

test("fetchStatus and fetchRoutes pass an abort signal so a dead connection times out", async () => {
  const options = [];
  globalThis.fetch = async (url, init) => {
    options.push(init);
    return { ok: true, json: async () => [] };
  };

  await fetchStatus();
  await fetchRoutes();

  assert.equal(options.length, 2);
  for (const init of options) {
    assert.ok(init.signal instanceof AbortSignal);
  }
});

test("a full routes load gets a long timeout while status and incremental fetches stay at 30 s", async () => {
  const realTimeout = AbortSignal.timeout;
  const timeouts = [];
  AbortSignal.timeout = (ms) => {
    timeouts.push(ms);
    return realTimeout.call(AbortSignal, ms);
  };
  globalThis.fetch = async () => ({ ok: true, json: async () => [] });
  try {
    await fetchRoutes();
    await fetchRoutes("2026-11-04T10:00:00+00:00");
    await fetchStatus();
  } finally {
    AbortSignal.timeout = realTimeout;
  }

  assert.deepEqual(timeouts, [120000, 30000, 30000]);
});

test("fetchShips calls the ships endpoint, with a since cursor when given", async () => {
  const { fetchShips } = await import("../js/api.js");
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [{ name: "Magog" }] };
  };

  assert.deepEqual(await fetchShips(), [{ name: "Magog" }]);
  await fetchShips("2026-11-04T12:00:05.000Z");

  assert.deepEqual(calls, ["api/uboats/ships", "api/uboats/ships?since=2026-11-04T12%3A00%3A05.000Z"]);
});

test("excludePoint posts the sequence as JSON and returns the patrol", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return { ok: true, json: async () => ({ external_id: "a/b" }) };
  };

  const result = await excludePoint("a/b", 3);

  assert.equal(calls[0][0], "api/uboats/routes/a%2Fb/excluded-points");
  assert.equal(calls[0][1].method, "POST");
  assert.equal(calls[0][1].headers["Content-Type"], "application/json");
  assert.equal(calls[0][1].body, JSON.stringify({ sequence: 3 }));
  assert.ok(calls[0][1].signal);
  assert.deepEqual(result, { external_id: "a/b" });
});

test("restorePoint sends DELETE with the sequence as JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return { ok: true, json: async () => ({ external_id: "p1" }) };
  };

  const result = await restorePoint("p1", 2);

  assert.equal(calls[0][0], "api/uboats/routes/p1/excluded-points");
  assert.equal(calls[0][1].method, "DELETE");
  assert.equal(calls[0][1].body, JSON.stringify({ sequence: 2 }));
  assert.deepEqual(result, { external_id: "p1" });
});

test("excludePoint rejects with a Dutch message on a 409", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 409, json: async () => ({ detail: "last point" }) });

  await assert.rejects(() => excludePoint("p1", 1), { message: "Dit is het laatste punt van deze patrouille." });
});

function silenceErrors(t) {
  const logged = [];
  t.mock.method(console, "error", (...args) => logged.push(args));
  return logged;
}

test("a failed edit shows only a Dutch message and logs the server detail", async (t) => {
  const logged = silenceErrors(t);
  globalThis.fetch = async () => ({ ok: false, status: 403, json: async () => ({ detail: "Editing is only allowed from this computer" }) });
  await assert.rejects(() => excludePoint("p1", 1), { message: "Uitsluiten mislukt" });
  assert.match(JSON.stringify(logged), /only allowed from this computer/);

  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => { throw new Error("no json"); } });
  await assert.rejects(() => excludePoint("p1", 1), { message: "Uitsluiten mislukt" });
  await assert.rejects(() => restorePoint("p1", 1), { message: "Herstellen mislukt" });
});

test("a timed out edit says it may still be processed, whatever the browser calls the error", async (t) => {
  const logged = silenceErrors(t);
  globalThis.fetch = async () => {
    throw new DOMException("signal timed out", "TimeoutError");
  };
  await assert.rejects(() => excludePoint("p1", 1), { message: "Dit duurt lang en wordt mogelijk nog verwerkt." });
  await assert.rejects(() => restorePoint("p1", 1), { message: "Dit duurt lang en wordt mogelijk nog verwerkt." });
  assert.equal(logged.length, 2);
});

test("a network failure while editing shows the Dutch failure string", async (t) => {
  silenceErrors(t);
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(() => excludePoint("p1", 1), { message: "Uitsluiten mislukt" });
  await assert.rejects(() => restorePoint("p1", 1), { message: "Herstellen mislukt" });
});

test("canEdit is false unless the status says so", () => {
  assert.equal(canEdit(null), false);
  assert.equal(canEdit({}), false);
  assert.equal(canEdit({ can_edit: false }), false);
  assert.equal(canEdit({ can_edit: true }), true);
});

test("fetchBoat asks for the encoded slug and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => ({ slug: "u 1" }) };
  };

  const result = await fetchBoat("u 1");

  assert.equal(calls[0], "api/uboats/boten/u%201");
  assert.deepEqual(result, { slug: "u 1" });
});

test("fetchBoat rejects when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 404 });

  await assert.rejects(() => fetchBoat("u1"), /Failed to fetch boat: 404/);
});

test("fetchAllRoutes reads pages until one comes back short, and reports progress", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    const offset = Number(new URL(url, "http://x").searchParams.get("offset"));
    const count = offset === 0 ? 2 : 1;
    return { ok: true, json: async () => Array.from({ length: count }, (_, i) => ({ external_id: `p${offset + i}` })) };
  };
  const progress = [];

  const pages = [];
  const routes = await fetchAllRoutes({ firstPageSize: 2, pageSize: 3, onProgress: (received) => progress.push(received), onPage: (page, last) => pages.push([page.length, last]) });

  assert.deepEqual(routes.map((route) => route.external_id), ["p0", "p1", "p2"]);
  assert.deepEqual(calls, ["api/uboats/routes?limit=2&offset=0", "api/uboats/routes?limit=3&offset=2"]);
  assert.deepEqual(pages, [[2, false], [1, true]]);
  assert.deepEqual(progress, [2, 3]);
});

test("fetchAllRoutes rejects when a page fails", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 500 });

  await assert.rejects(() => fetchAllRoutes({ firstPageSize: 2 }), /Failed to fetch routes: 500/);
});

test("fetchShip asks for the encoded ship id and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => ({ ship_external_id: "4 8" }) };
  };

  const result = await fetchShip("4 8");

  assert.equal(calls[0], "api/uboats/ships/4%208");
  assert.deepEqual(result, { ship_external_id: "4 8" });
});

test("fetchShip rejects when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 404 });

  await assert.rejects(() => fetchShip("408"), /Failed to fetch ship: 404/);
});

test("fetchBattlePositions returns the parsed list", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [{ title: "A", lat: 1, lng: 2 }] };
  };

  assert.deepEqual(await fetchBattlePositions(), [{ title: "A", lat: 1, lng: 2 }]);
  assert.equal(calls[0], "api/battles/positions");
});

test("saveBattlePosition PUTs the encoded title with the coordinates", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return { ok: true, json: async () => ({ title: 'Operation "Weserübung"', lat: 1, lng: 2 }) };
  };

  const result = await saveBattlePosition('Operation "Weserübung"', 1, 2);

  assert.equal(calls[0][0], `api/battles/positions/${encodeURIComponent('Operation "Weserübung"')}`);
  assert.equal(calls[0][1].method, "PUT");
  assert.deepEqual(JSON.parse(calls[0][1].body), { lat: 1, lng: 2 });
  assert.deepEqual(result, { title: 'Operation "Weserübung"', lat: 1, lng: 2 });
});

test("clearBattlePosition DELETEs the encoded title", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return { ok: true, status: 204 };
  };

  await clearBattlePosition('Operation "Weserübung"');

  assert.equal(calls[0][0], `api/battles/positions/${encodeURIComponent('Operation "Weserübung"')}`);
  assert.equal(calls[0][1].method, "DELETE");
});

test("the battle position helpers reject when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 403 });

  await assert.rejects(() => fetchBattlePositions(), /403/);
  await assert.rejects(() => saveBattlePosition("A", 1, 2), /403/);
  await assert.rejects(() => clearBattlePosition("A"), /403/);
});

test("fetchArticle returns the article, null on 404 and rejects on other errors", async () => {
  const { fetchArticle } = await import("../js/api.js");
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, status: 200, json: async () => ({ title: "A & B", html: "<p>x</p>", url: "u" }) };
  };
  assert.deepEqual(await fetchArticle("A & B"), { title: "A & B", html: "<p>x</p>", url: "u" });
  assert.deepEqual(calls, ["api/battles/articles/A%20%26%20B"]);
  await fetchArticle("Бітва", "be", "nl");
  await fetchArticle("Kursk", "en", "nl");
  assert.deepEqual(calls.slice(1), [
    "api/battles/articles/%D0%91%D1%96%D1%82%D0%B2%D0%B0?lang=be&versie=nl",
    "api/battles/articles/Kursk?versie=nl",
  ]);

  globalThis.fetch = async () => ({ ok: false, status: 404 });
  assert.equal(await fetchArticle("Nope"), null);

  globalThis.fetch = async () => ({ ok: false, status: 502 });
  await assert.rejects(fetchArticle("Down"), /502/);
});

test("fetchPlaces encodes the query, passes the signal and returns the places", async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options.signal]);
    return { ok: true, json: async () => [{ name: "Narvik" }] };
  };
  const { fetchPlaces } = await import("../js/api.js");
  const controller = new AbortController();

  const result = await fetchPlaces("Nar vik&", { signal: controller.signal });

  assert.equal(calls[0][0], "api/places?q=Nar%20vik%26");
  assert.ok(calls[0][1] instanceof AbortSignal);
  assert.deepEqual(result, [{ name: "Narvik" }]);
  controller.abort();
  assert.ok(calls[0][1].aborted);
});

test("fetchPlaces throws on a status other than 200", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 503 });
  const { fetchPlaces } = await import("../js/api.js");
  await assert.rejects(fetchPlaces("nar", {}), /503/);
});


test("fetchArticle asks for the language when it is not English", async () => {
  const { fetchArticle } = await import("../js/api.js");
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, status: 200, json: async () => ({}) };
  };
  await fetchArticle("Slag om K", "nl");
  await fetchArticle("Kursk", "en");
  await fetchArticle("Kursk");
  assert.deepEqual(calls, ["api/battles/articles/Slag%20om%20K?lang=nl", "api/battles/articles/Kursk",
    "api/battles/articles/Kursk"]);
});

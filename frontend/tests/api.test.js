import { test } from "node:test";
import assert from "node:assert/strict";

import { canEdit, excludePoint, fetchBoats, fetchRoutes, fetchStatus, restorePoint } from "../js/api.js";

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

test("excludePoint and restorePoint use the API detail, else a fallback", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 403, json: async () => ({ detail: "Alleen lokaal" }) });
  await assert.rejects(() => excludePoint("p1", 1), { message: "Alleen lokaal" });

  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => { throw new Error("no json"); } });
  await assert.rejects(() => excludePoint("p1", 1), { message: "Uitsluiten mislukt" });
  await assert.rejects(() => restorePoint("p1", 1), { message: "Herstellen mislukt" });
});

test("canEdit is false unless the status says so", () => {
  assert.equal(canEdit(null), false);
  assert.equal(canEdit({}), false);
  assert.equal(canEdit({ can_edit: false }), false);
  assert.equal(canEdit({ can_edit: true }), true);
});

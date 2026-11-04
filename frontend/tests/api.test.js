import { test } from "node:test";
import assert from "node:assert/strict";

import { fetchBoats, fetchRoutes, fetchStatus } from "../js/api.js";

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

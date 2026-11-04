import { test } from "node:test";
import assert from "node:assert/strict";

import { mergeRoutes, statusLine, startPolling } from "../js/live.js";

const NOW = new Date("2026-11-04T12:00:12Z");
const last = (crawled_at = "2026-11-04T12:00:00Z") => ({
  boat_slug: "u-99",
  boat_number: "U-99",
  external_id: "p1",
  crawled_at,
});

test("mergeRoutes replaces a patrol by external_id and appends new ones", () => {
  const routes = [
    { external_id: "a", v: 1 },
    { external_id: "b", v: 1 },
  ];
  const merged = mergeRoutes(routes, [
    { external_id: "b", v: 2 },
    { external_id: "c", v: 1 },
  ]);
  assert.deepEqual(merged, [
    { external_id: "a", v: 1 },
    { external_id: "b", v: 2 },
    { external_id: "c", v: 1 },
  ]);
  assert.equal(routes[1].v, 1);
});

test("statusLine shows progress and the last boat", () => {
  const status = { listing_total: 1153, boats_crawled: 47, boats_failed: 0, last_patrol: last() };
  assert.equal(statusLine(status, NOW), "47 van 1153 boten · laatste: U-99, 12 sec geleden");
});

test("statusLine adds failures only when there are any", () => {
  const status = { listing_total: 1153, boats_crawled: 47, boats_failed: 2, last_patrol: last() };
  assert.equal(
    statusLine(status, NOW),
    "47 van 1153 boten · laatste: U-99, 12 sec geleden · 2 mislukt",
  );
});

test("statusLine without a total", () => {
  const status = { listing_total: null, boats_crawled: 47, boats_failed: 0, last_patrol: last() };
  assert.equal(statusLine(status, NOW), "47 boten · laatste: U-99, 12 sec geleden");
  assert.equal(statusLine({ ...status, last_patrol: null }, NOW), "47 boten");
});

test("statusLine with no last patrol", () => {
  const status = { listing_total: null, boats_crawled: 0, boats_failed: 0, last_patrol: null };
  assert.equal(statusLine(status, NOW), "0 boten");
});

test("statusLine age units and negative clamp", () => {
  const at = (iso) => ({ listing_total: null, boats_crawled: 1, boats_failed: 0, last_patrol: last(iso) });
  assert.match(statusLine(at("2026-11-04T11:56:12Z"), NOW), /4 min geleden$/);
  assert.match(statusLine(at("2026-11-04T10:00:12Z"), NOW), /2 uur geleden$/);
  assert.match(statusLine(at("2026-10-31T12:00:12Z"), NOW), /4 dagen geleden$/);
  assert.match(statusLine(at("2026-11-04T12:05:00Z"), NOW), /0 sec geleden$/);
});

function harness({ statuses, routesResult = [], hidden = false, failStatus = false, failRoutes = false }) {
  const log = { routeCalls: [], data: [], status: [], errors: [], timers: [] };
  let i = 0;
  const opts = {
    intervalMs: 5000,
    fetchStatus: async () => {
      if (failStatus) throw new Error("status down");
      return statuses[Math.min(i++, statuses.length - 1)];
    },
    fetchRoutes: async (since) => {
      log.routeCalls.push(since);
      if (failRoutes) throw new Error("routes down");
      return routesResult;
    },
    isHidden: () => hidden,
    onData: (d) => log.data.push(d),
    onStatus: (s) => log.status.push(s),
    onError: (e) => log.errors.push(e),
    setTimer: (fn, ms) => log.timers.push({ fn, ms }),
  };
  return { opts, log };
}
const st = (revision) => ({ revision });

test("poll does not fetch routes when the revision is unchanged", async () => {
  const { opts, log } = harness({ statuses: [st("r1"), st("r1")] });
  startPolling(opts);
  await new Promise((r) => setImmediate(r));
  await log.timers[0].fn();
  assert.deepEqual(log.routeCalls, [null]);
  assert.equal(log.status.length, 2);
  assert.equal(log.timers.length, 2);
});

test("poll fetches routes since the previous revision when it changes", async () => {
  const { opts, log } = harness({ statuses: [st("r1"), st("r2")], routesResult: [{ external_id: "x" }] });
  startPolling(opts);
  await new Promise((r) => setImmediate(r));
  await log.timers[0].fn();
  assert.deepEqual(log.routeCalls, [null, "r1"]);
  assert.equal(log.data.length, 2);
  assert.equal(log.timers[0].ms, 5000);
});

test("poll with a null previous revision fetches all routes", async () => {
  const { opts, log } = harness({ statuses: [st(null), st(null)] });
  startPolling(opts);
  await new Promise((r) => setImmediate(r));
  await log.timers[0].fn();
  assert.deepEqual(log.routeCalls, [null]);
  assert.equal(log.data.length, 1);
});

test("poll skips the request while the tab is hidden", async () => {
  const { opts, log } = harness({ statuses: [st("r1")], hidden: true });
  startPolling(opts);
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(log.routeCalls, []);
  assert.equal(log.status.length, 0);
  assert.equal(log.timers.length, 1);
});

test("poll reports an error, keeps polling and does not call onData", async () => {
  const { opts, log } = harness({ statuses: [st("r1")], failRoutes: true });
  startPolling(opts);
  await new Promise((r) => setImmediate(r));
  assert.equal(log.errors.length, 1);
  assert.equal(log.data.length, 0);
  assert.equal(log.timers.length, 1);
  await log.timers[0].fn();
  assert.deepEqual(log.routeCalls, [null, null]); // retried
});

test("poll reports a status failure and keeps polling", async () => {
  const { opts, log } = harness({ statuses: [], failStatus: true });
  startPolling(opts);
  await new Promise((r) => setImmediate(r));
  assert.equal(log.errors.length, 1);
  assert.equal(log.timers.length, 1);
});

test("stop prevents further polls", async () => {
  const { opts, log } = harness({ statuses: [st("r1")] });
  const { stop } = startPolling(opts);
  await new Promise((r) => setImmediate(r));
  stop();
  await log.timers[0].fn();
  assert.equal(log.status.length, 1);
  assert.equal(log.timers.length, 1);
});

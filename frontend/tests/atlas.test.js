import { test } from "node:test";
import assert from "node:assert/strict";

import { atlasMapFor } from "../js/atlas.js";

const maps = [
  { date: "1939-09-01", file: "a" },
  { date: "1940-05-01", file: "b" },
  { date: "1941-12-01", file: "c" },
];

test("atlasMapFor picks the last map on or before the date", () => {
  assert.equal(atlasMapFor(maps, "1939-09-01").file, "a");
  assert.equal(atlasMapFor(maps, "1940-04-30").file, "a");
  assert.equal(atlasMapFor(maps, "1940-05-01").file, "b");
  assert.equal(atlasMapFor(maps, "1945-05-01").file, "c");
});

test("atlasMapFor has no map before the first one", () => {
  assert.equal(atlasMapFor(maps, "1939-08-31"), null);
});

test("atlasMapFor handles an empty list", () => {
  assert.equal(atlasMapFor([], "1940-01-01"), null);
});

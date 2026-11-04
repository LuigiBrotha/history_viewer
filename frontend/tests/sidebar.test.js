import { test } from "node:test";
import assert from "node:assert/strict";

import { boatsHeading } from "../js/sidebar.js";

test("boatsHeading shows how many boats are active", () => {
  assert.equal(boatsHeading(33), "Actieve boten (33)");
  assert.equal(boatsHeading(0), "Actieve boten (0)");
});

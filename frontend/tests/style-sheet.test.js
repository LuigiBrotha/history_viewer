import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("every block in the style sheet is closed, so no later rule is silently lost", () => {
  const css = readFileSync(new URL("../css/style.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  let depth = 0;
  for (const character of css) {
    if (character === "{") depth += 1;
    if (character === "}") depth -= 1;
    assert.ok(depth >= 0);
  }
  assert.equal(depth, 0);
});

test("marker icons keep Leaflet's absolute position, or each one is pushed down by the markers before it", () => {
  const css = readFileSync(new URL("../css/style.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (selector.split(",").some((part) => /^\s*\.battle-square\s*$/.test(part))) {
      assert.doesNotMatch(body, /position\s*:/);
    }
  }
});

test("the article column is sized by the custom property that initBattleSplit sets", () => {
  const css = readFileSync(new URL("../css/style.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const split = readFileSync(new URL("../js/battle-split.js", import.meta.url), "utf8");
  const property = /setProperty\("(--[\w-]+)"/.exec(split)[1];
  const bodies = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter(([, selector]) => selector.trim() === "#article-pane").map(([, , body]) => body);
  assert.ok(bodies.some((body) => body.includes(`var(${property},`)));
});

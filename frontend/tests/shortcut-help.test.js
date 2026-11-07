import { test } from "node:test";
import assert from "node:assert/strict";

import { createShortcutHelp } from "../js/shortcut-help.js";
import { SHORTCUTS } from "../js/shortcuts.js";
import { Element, installDom } from "./battle-dom.js";

test("the help lists every shortcut, toggles, and closes on its button", () => {
  installDom();
  const body = new Element("body");
  const help = createShortcutHelp({ parentEl: body });
  const box = body.byClass("shortcut-help")[0];
  assert.equal(box.hidden, true);
  help.toggle();
  assert.equal(box.hidden, false);
  assert.equal(box.byClass("shortcut-row").length, SHORTCUTS.length);
  assert.match(box.byClass("shortcut-row")[4].textContent + box.byClass("shortcut-keys")[4].textContent, /Shift\+Enter/);
  box.byClass("shortcut-help-close")[0].dispatch("click");
  assert.equal(box.hidden, true);
  help.toggle();
  help.toggle();
  assert.equal(box.hidden, true);
});

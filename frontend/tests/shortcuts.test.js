import { test } from "node:test";
import assert from "node:assert/strict";

import { SHORTCUTS, installShortcuts } from "../js/shortcuts.js";

function target(tag = "div", { role = null, editable = false } = {}) {
  return {
    tagName: tag.toUpperCase(),
    isContentEditable: editable,
    closest: (selector) => (role && selector.includes(`[role="${role}"]`) ? {} : null),
  };
}

function setup() {
  const listeners = [];
  const doc = {
    addEventListener: (type, fn, options) => listeners.push({ type, fn, capture: options?.capture ?? options === true }),
  };
  const calls = [];
  const actions = new Proxy({}, { get: (_, name) => (...args) => calls.push([name, ...args]) });
  installShortcuts({ doc, actions });
  const press = (key, { shiftKey = false, ctrlKey = false, altKey = false, metaKey = false, on = target() } = {}) => {
    const event = {
      key, shiftKey, ctrlKey, altKey, metaKey, target: on, defaultPrevented: false, stopped: false,
      preventDefault() { this.defaultPrevented = true; },
      stopPropagation() { this.stopped = true; },
    };
    for (const listener of listeners) listener.fn(event);
    return event;
  };
  return { listeners, calls, press };
}

test("the listener runs in the capture phase, before the map sees the key", () => {
  const { listeners } = setup();
  assert.equal(listeners.length, 1);
  assert.equal(listeners[0].type, "keydown");
  assert.equal(listeners[0].capture, true);
});

test("arrow up and down choose the previous and next battle and keep the map from panning", () => {
  const { calls, press } = setup();
  const down = press("ArrowDown");
  press("ArrowUp");
  assert.deepEqual(calls, [["next"], ["previous"]]);
  assert.equal(down.defaultPrevented, true);
  assert.equal(down.stopped, true);
});

test("the letter keys, Enter and the question mark call their actions", () => {
  const { calls, press } = setup();
  press("p");
  press("Enter");
  press("Enter", { shiftKey: true });
  press("w");
  press("a");
  press("v");
  press("/");
  press("?", { shiftKey: true });
  press("P");
  assert.deepEqual(calls.map(([name]) => name), [
    "editPosition", "save", "saveAndNext", "clearPosition", "toggleArticle", "togglePane", "focusSearch", "toggleHelp",
    "editPosition",
  ]);
});

test("nothing happens while typing, on sliders and dividers, or with Ctrl, Alt or Meta", () => {
  const { calls, press } = setup();
  press("ArrowDown", { on: target("input") });
  press("p", { on: target("textarea") });
  press("p", { on: target("div", { editable: true }) });
  press("ArrowDown", { on: target("div", { role: "slider" }) });
  press("ArrowUp", { on: target("div", { role: "separator" }) });
  press("p", { ctrlKey: true });
  press("a", { altKey: true });
  press("v", { metaKey: true });
  press("x");
  assert.deepEqual(calls, []);
});

test("Enter on a button keeps doing what the button does", () => {
  const { calls, press } = setup();
  press("Enter", { on: target("button") });
  press("Enter", { on: target("a") });
  assert.deepEqual(calls, []);
});

test("the help lists every shortcut with a Dutch description", () => {
  assert.ok(SHORTCUTS.length >= 9);
  for (const { keys, text } of SHORTCUTS) {
    assert.ok(keys.length > 0 && text.length > 0);
  }
  assert.ok(SHORTCUTS.some(({ keys }) => keys.includes("Shift+Enter")));
});

import { pageActions } from "../js/shortcuts.js";

test("pageActions sends each key to the battles, the search field or the help", () => {
  const calls = [];
  const battles = new Proxy({}, { get: (_, name) => (...args) => calls.push([name, ...args]) });
  const actions = pageActions({
    battles: () => battles,
    search: () => ({ focus: () => calls.push(["focus"]) }),
    help: { toggle: () => calls.push(["help"]) },
  });
  for (const name of ["next", "previous", "editPosition", "save", "saveAndNext", "clearPosition", "toggleArticle",
    "togglePane", "focusSearch", "toggleHelp"]) {
    actions[name]();
  }
  assert.deepEqual(calls, [["step", 1], ["step", -1], ["editSelected"], ["save"], ["saveAndNext"], ["clearSelected"],
    ["toggleArticle"], ["togglePane"], ["focus"], ["help"]]);
});

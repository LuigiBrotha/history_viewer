import { test } from "node:test";
import assert from "node:assert/strict";

import { createRouteToggle } from "../js/route-toggle.js";

function fakeDoc() {
  return {
    createElement() {
      const handlers = {};
      return {
        attributes: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(type, handler) { handlers[type] = handler; },
        click() { handlers.click(); },
      };
    },
  };
}

function setup(visible) {
  let control;
  globalThis.L = {
    control: () => (control = { addTo() { this.element = this.onAdd(); } }),
    DomEvent: { disableClickPropagation() {} },
  };
  const changes = [];
  const toggle = createRouteToggle({ map: {}, doc: fakeDoc(), visible, onChange: (shown) => changes.push(shown) });
  return { toggle, changes, button: control.element };
}

test("the button sits in the map controls and starts as the URL said", () => {
  const { button, changes } = setup(false);
  assert.equal(button.textContent, "Routes");
  assert.equal(button.attributes["aria-pressed"], "false");
  assert.deepEqual(changes, [false]);
});

test("clicking switches the routes off and on again", () => {
  const { button, changes } = setup(true);
  button.click();
  assert.equal(button.attributes["aria-pressed"], "false");
  button.click();
  assert.equal(button.attributes["aria-pressed"], "true");
  assert.deepEqual(changes, [true, false, true]);
});

test("asking for routes that already show changes nothing", () => {
  const { toggle, changes } = setup(true);
  toggle.show();
  assert.deepEqual(changes, [true]);
});

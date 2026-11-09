import { test } from "node:test";
import assert from "node:assert/strict";

import { createBoatToggle, createNamesToggle, createRouteToggle, createShipsToggle } from "../js/map-toggle.js";

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

function setup(visible, create = createRouteToggle) {
  let control;
  globalThis.L = {
    control: () => (control = { addTo() { this.element = this.onAdd(); } }),
    DomEvent: { disableClickPropagation() {} },
  };
  const changes = [];
  const toggle = create({ map: {}, doc: fakeDoc(), visible, onChange: (shown) => changes.push(shown) });
  return { toggle, changes, button: control.element };
}

test("the button sits in the map controls and starts as the URL said", () => {
  const { button, changes } = setup(false);
  assert.equal(button.id, "route-toggle");
  assert.equal(button.textContent, "Routes");
  assert.equal(button.attributes["aria-pressed"], "false");
  assert.deepEqual(changes, [false]);
});

test("the U-boats have a button of their own", () => {
  const { button, changes } = setup(true, createBoatToggle);
  assert.equal(button.id, "boat-toggle");
  assert.equal(button.textContent, "U-boten");
  button.click();
  assert.deepEqual(changes, [true, false]);
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

test("the names button tells the battles and keeps the choice in the URL", () => {
  const seen = [];
  const writes = [];
  const { button } = setup(false, ({ map, doc, visible }) => createNamesToggle({
    map, doc, shown: visible,
    battles: { setNamesVisible: (shown) => seen.push(shown) },
    urlSync: { update: (partial) => writes.push(partial) },
  }));
  assert.equal(button.textContent, "Namen");
  assert.deepEqual(writes, [{ namesOff: true }]);
  button.click();
  assert.deepEqual(seen, [false, true]);
  assert.deepEqual(writes, [{ namesOff: true }, { namesOff: null }]);
});

test("the ships button tells the layer and keeps the choice in the URL", () => {
  const seen = [];
  const writes = [];
  const { button } = setup(true, ({ map, doc, visible }) => createShipsToggle({
    map, doc, shown: visible,
    shipLayer: { setVisible: (shown) => seen.push(shown) },
    urlSync: { update: (partial) => writes.push(partial) },
  }));
  assert.equal(button.id, "ships-toggle");
  assert.equal(button.textContent, "Schepen");
  button.click();
  assert.deepEqual(seen, [true, false]);
  assert.deepEqual(writes, [{ shipsOff: null }, { shipsOff: true }]);
});

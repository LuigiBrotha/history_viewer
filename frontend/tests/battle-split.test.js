import { test } from "node:test";
import assert from "node:assert/strict";

import {
  KEY_STEP_PX,
  clampSize,
  defaultSize,
  initBattleSplit,
  isPhone,
  keySize,
  loadState,
  paneSizeFromPointer,
  saveState,
  startsOpen,
} from "../js/battle-split.js";
import { Element, fakeStorage } from "./battle-dom.js";

test("below 700px the pane sits under the map", () => {
  assert.equal(isPhone(699), true);
  assert.equal(isPhone(700), false);
});

test("the pane is 240px to 80% of the window wide, or 120px to 75% of the split high on a phone", () => {
  assert.equal(clampSize(100, 1000, false), 240);
  assert.equal(clampSize(900, 1000, false), 800);
  assert.equal(clampSize(500, 1000, false), 500);
  assert.equal(clampSize(100, 800, true), 120);
  assert.equal(clampSize(790, 800, true), 600);
  assert.equal(clampSize(1000, 280, false), 240);
});

test("the default size is a usable share of the room", () => {
  assert.equal(defaultSize(false, 1200), 360);
  assert.equal(defaultSize(false, 400), 320);
  assert.equal(defaultSize(true, 600), 240);
});

test("the pane starts hidden under 900px unless the user chose otherwise", () => {
  assert.equal(startsOpen(899, {}), false);
  assert.equal(startsOpen(900, {}), true);
  assert.equal(startsOpen(500, { open: true }), true);
  assert.equal(startsOpen(1400, { open: false }), false);
});

test("state is kept in storage and a broken storage is no problem", () => {
  const storage = fakeStorage();
  saveState(storage, { open: true, width: 400, height: 200 });
  assert.deepEqual(loadState(storage), { open: true, width: 400, height: 200 });
  assert.deepEqual(loadState(fakeStorage({ "uboats.battlePane": "{broken" })), {});
  assert.deepEqual(loadState(fakeStorage({ "uboats.battlePane": "[1]" })), {});
  const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.deepEqual(loadState(throwing), {});
  assert.doesNotThrow(() => saveState(throwing, { open: true }));
  assert.deepEqual(loadState(null), {});
});

test("a drag sets the size from the pointer to the far edge of the split", () => {
  const rect = { left: 0, top: 100, right: 1000, bottom: 700 };
  assert.equal(paneSizeFromPointer({ x: 640, y: 0 }, rect, false), 360);
  assert.equal(paneSizeFromPointer({ x: 0, y: 400 }, rect, true), 300);
});

test("arrow keys move the divider: left or up widens the pane", () => {
  assert.equal(keySize("ArrowLeft", 300, false, false), 300 + KEY_STEP_PX);
  assert.equal(keySize("ArrowRight", 300, false, false), 300 - KEY_STEP_PX);
  assert.equal(keySize("ArrowRight", 300, false, true), 300 - KEY_STEP_PX * 4);
  assert.equal(keySize("ArrowUp", 300, true, false), 300 + KEY_STEP_PX);
  assert.equal(keySize("ArrowDown", 300, true, false), 300 - KEY_STEP_PX);
  assert.equal(keySize("ArrowUp", 300, false, false), null);
  assert.equal(keySize("a", 300, false, false), null);
});

function setup({ width = 1200, height = 800, stored = {} } = {}) {
  const win = {
    innerWidth: width,
    innerHeight: height,
    listeners: {},
    addEventListener(type, handler) {
      this.listeners[type] = handler;
    },
    requestAnimationFrame: (fn) => fn(),
  };
  const splitEl = new Element("div");
  splitEl.rect = { left: 0, top: 0, right: width, bottom: height, width, height };
  const paneEl = new Element("aside");
  const dividerEl = new Element("div");
  const toggleEl = new Element("button");
  const map = { sizes: 0, invalidateSize() { this.sizes += 1; } };
  const storage = fakeStorage(stored.raw ?? {});
  const split = initBattleSplit({ splitEl, paneEl, dividerEl, toggleEl, map, storage, win });
  return { win, splitEl, paneEl, dividerEl, toggleEl, map, storage, split };
}

test("on a wide window the pane starts open with the default width", () => {
  const { splitEl, paneEl, dividerEl, toggleEl } = setup();
  assert.equal(splitEl.classes.has("pane-hidden"), false);
  assert.equal(paneEl.styleProps["--battle-pane-size"], "360px");
  assert.equal(dividerEl.getAttribute("aria-orientation"), "vertical");
  assert.equal(dividerEl.getAttribute("aria-valuenow"), "360");
  assert.equal(dividerEl.getAttribute("aria-valuemin"), "240");
  assert.equal(dividerEl.getAttribute("aria-valuemax"), "960");
  assert.equal(toggleEl.getAttribute("aria-expanded"), "true");
});

test("on a narrow window the pane starts hidden", () => {
  const { splitEl, toggleEl } = setup({ width: 800 });
  assert.equal(splitEl.classes.has("pane-hidden"), true);
  assert.equal(toggleEl.getAttribute("aria-expanded"), "false");
});

test("the toggle shows and hides the pane, stores it and resizes the map", () => {
  const { splitEl, toggleEl, map, storage } = setup();
  const before = map.sizes;
  toggleEl.dispatch("click");
  assert.equal(splitEl.classes.has("pane-hidden"), true);
  assert.ok(map.sizes > before);
  assert.equal(JSON.parse(storage.data["uboats.battlePane"]).open, false);
  toggleEl.dispatch("click");
  assert.equal(splitEl.classes.has("pane-hidden"), false);
  assert.equal(JSON.parse(storage.data["uboats.battlePane"]).open, true);
});

test("the stored size is used on the next visit", () => {
  const raw = { "uboats.battlePane": JSON.stringify({ open: true, width: 500, height: 300 }) };
  const { paneEl } = setup({ width: 800, stored: { raw } });
  assert.equal(paneEl.styleProps["--battle-pane-size"], "500px");
});

test("dragging the divider resizes the pane while the map follows, and stores the size at the end", () => {
  const { dividerEl, paneEl, map, storage, splitEl } = setup();
  dividerEl.dispatch("pointerdown", { pointerId: 1, clientX: 840, clientY: 0 });
  assert.equal(splitEl.classes.has("resizing"), true);
  const before = map.sizes;
  dividerEl.dispatch("pointermove", { pointerId: 1, clientX: 700, clientY: 0 });
  assert.equal(paneEl.styleProps["--battle-pane-size"], "500px");
  assert.ok(map.sizes > before);
  dividerEl.dispatch("pointermove", { pointerId: 1, clientX: 1190, clientY: 0 });
  assert.equal(paneEl.styleProps["--battle-pane-size"], "240px");
  dividerEl.dispatch("pointerup", { pointerId: 1 });
  assert.equal(splitEl.classes.has("resizing"), false);
  assert.equal(JSON.parse(storage.data["uboats.battlePane"]).width, 240);
  dividerEl.dispatch("pointermove", { pointerId: 1, clientX: 600, clientY: 0 });
  assert.equal(paneEl.styleProps["--battle-pane-size"], "240px");
});

test("a pointer that is not dragging does not resize", () => {
  const { dividerEl, paneEl } = setup();
  dividerEl.dispatch("pointermove", { pointerId: 1, clientX: 100, clientY: 0 });
  assert.equal(paneEl.styleProps["--battle-pane-size"], "360px");
});

test("arrow keys on the divider resize it and ignore other keys", () => {
  const { dividerEl, paneEl } = setup();
  const event = dividerEl.dispatch("keydown", { key: "ArrowLeft" });
  assert.equal(event.defaultPrevented, true);
  assert.equal(paneEl.styleProps["--battle-pane-size"], `${360 + KEY_STEP_PX}px`);
  const other = dividerEl.dispatch("keydown", { key: "a" });
  assert.equal(other.defaultPrevented, undefined);
});

test("on a phone the divider drags the height and says it is horizontal", () => {
  const { dividerEl, paneEl } = setup({ width: 400, height: 800, stored: { raw: { "uboats.battlePane": JSON.stringify({ open: true }) } } });
  assert.equal(dividerEl.getAttribute("aria-orientation"), "horizontal");
  dividerEl.dispatch("pointerdown", { pointerId: 2, clientX: 0, clientY: 500 });
  dividerEl.dispatch("pointermove", { pointerId: 2, clientX: 0, clientY: 400 });
  assert.equal(paneEl.styleProps["--battle-pane-size"], "400px");
  dividerEl.dispatch("pointerup", { pointerId: 2 });
});

test("turning the window from wide to narrow switches to the phone layout and resizes the map", () => {
  const { win, dividerEl, map, paneEl } = setup();
  const before = map.sizes;
  win.innerWidth = 600;
  win.innerHeight = 800;
  win.listeners.resize();
  assert.equal(dividerEl.getAttribute("aria-orientation"), "horizontal");
  assert.ok(map.sizes > before);
  assert.equal(paneEl.styleProps["--battle-pane-size"], "320px");
});

test("open, close and isOpen are available to other modules", () => {
  const { split, splitEl } = setup({ width: 800 });
  assert.equal(split.isOpen(), false);
  split.open();
  assert.equal(split.isOpen(), true);
  assert.equal(splitEl.classes.has("pane-hidden"), false);
  split.open();
  assert.equal(split.isOpen(), true);
  split.close();
  assert.equal(split.isOpen(), false);
});

const DEFAULT_STORAGE_KEY = "uboats.battlePane";
const PHONE_MAX_WIDTH = 699;
const OPEN_BY_DEFAULT_MIN_WIDTH = 900;
const MIN_WIDTH = 240;
const MAX_WIDTH_SHARE = 0.8;
const MIN_HEIGHT = 120;
const MIN_MAP_WIDTH = 320;
const MAX_HEIGHT_SHARE = 0.75;
const DEFAULT_WIDTH = 360;
const DEFAULT_HEIGHT_SHARE = 0.4;
export const KEY_STEP_PX = 24;
const KEY_SHIFT_FACTOR = 4;

export function isPhone(windowWidth) {
  return windowWidth <= PHONE_MAX_WIDTH;
}

// available is the window width beside the map, or the height of the split under it.
// reserved is the width of the other pane beside the map; the map keeps MIN_MAP_WIDTH of it.
export function clampSize(size, available, phone, reserved = 0) {
  const min = phone ? MIN_HEIGHT : MIN_WIDTH;
  let max = available * (phone ? MAX_HEIGHT_SHARE : MAX_WIDTH_SHARE);
  if (!phone && reserved > 0) max = Math.min(max, available - reserved - MIN_MAP_WIDTH);
  return Math.round(Math.max(min, Math.min(size, max)));
}

export function defaultSize(phone, available, defaultWidth = DEFAULT_WIDTH) {
  return clampSize(phone ? available * DEFAULT_HEIGHT_SHARE : defaultWidth, available, phone);
}

// Without a choice of the user the pane starts hidden on a narrow window, which is mostly map.
export function startsOpen(windowWidth, state) {
  return typeof state.open === "boolean" ? state.open : windowWidth >= OPEN_BY_DEFAULT_MIN_WIDTH;
}

export function loadState(storage, key = DEFAULT_STORAGE_KEY) {
  try {
    const state = JSON.parse(storage.getItem(key));
    return state !== null && typeof state === "object" && !Array.isArray(state) ? state : {};
  } catch {
    return {};
  }
}

export function saveState(storage, state, key = DEFAULT_STORAGE_KEY) {
  try {
    storage.setItem(key, JSON.stringify(state));
  } catch {
    // Without storage the pane just starts in its default state next time.
  }
}

// The pane lies at the far side of the divider: right of it on a wide window, below it on a phone.
export function paneSizeFromPointer(pointer, rect, phone) {
  return phone ? rect.bottom - pointer.y : rect.right - pointer.x;
}

// The new pane size for an arrow key, or null for any other key.
export function keySize(key, size, phone, shift) {
  const grow = phone ? "ArrowUp" : "ArrowLeft";
  const shrink = phone ? "ArrowDown" : "ArrowRight";
  const step = KEY_STEP_PX * (shift ? KEY_SHIFT_FACTOR : 1);
  if (key === grow) return size + step;
  if (key === shrink) return size - step;
  return null;
}

// Binds the pure logic above to the split: the pane, its divider and the button that
// shows it (toggleEl may be null when something else opens it). The map is told about
// every change of size, as it keeps its own pixel size. reserved() gives the pixels the
// other pane takes beside the map, so the map keeps a minimum width. With persistOpen false the pane
// always starts closed and its open state is neither read nor stored; only its size is.
export function initBattleSplit({
  splitEl,
  paneEl,
  dividerEl,
  toggleEl,
  map,
  storage,
  win = window,
  storageKey = DEFAULT_STORAGE_KEY,
  defaultWidth = DEFAULT_WIDTH,
  persistOpen = true,
  reserved = () => 0,
}) {
  const state = loadState(storage, storageKey);
  if (!persistOpen) delete state.open;
  let open = persistOpen ? startsOpen(win.innerWidth, state) : false;
  let dragging = null;
  let frame = false;

  const phone = () => isPhone(win.innerWidth);
  const taken = () => (phone() ? 0 : reserved());
  const available = () => (phone() ? splitEl.getBoundingClientRect().height : win.innerWidth);

  function size() {
    const stored = phone() ? state.height : state.width;
    return clampSize(typeof stored === "number" ? stored : defaultSize(phone(), available(), defaultWidth), available(), phone(), taken());
  }

  let current = size();

  function resizeMap() {
    map.invalidateSize();
  }

  function apply() {
    const isPhoneLayout = phone();
    const room = available();
    splitEl.classList.toggle("pane-hidden", !open);
    paneEl.style.setProperty("--battle-pane-size", `${current}px`);
    dividerEl.setAttribute("aria-orientation", isPhoneLayout ? "horizontal" : "vertical");
    dividerEl.setAttribute("aria-valuenow", String(current));
    dividerEl.setAttribute("aria-valuemin", String(clampSize(0, room, isPhoneLayout, taken())));
    dividerEl.setAttribute("aria-valuemax", String(clampSize(Infinity, room, isPhoneLayout, taken())));
    toggleEl?.setAttribute("aria-expanded", String(open));
  }

  function remember() {
    if (persistOpen) state.open = open;
    state[phone() ? "height" : "width"] = current;
    saveState(storage, state, storageKey);
  }

  function setSize(next) {
    current = clampSize(next, available(), phone(), taken());
    apply();
  }

  // One map resize per frame while dragging; the pane itself follows every event.
  function resizeMapSoon() {
    if (frame) return;
    frame = true;
    win.requestAnimationFrame(() => {
      frame = false;
      resizeMap();
    });
  }

  function setOpen(next) {
    open = next;
    if (open) current = size();
    apply();
    remember();
    resizeMap();
  }

  toggleEl?.addEventListener("click", () => setOpen(!open));

  dividerEl.addEventListener("pointerdown", (event) => {
    dragging = event.pointerId;
    dividerEl.setPointerCapture?.(event.pointerId);
    splitEl.classList.add("resizing");
    event.preventDefault?.();
  });

  dividerEl.addEventListener("pointermove", (event) => {
    if (dragging !== event.pointerId) return;
    setSize(paneSizeFromPointer({ x: event.clientX, y: event.clientY }, splitEl.getBoundingClientRect(), phone()));
    resizeMapSoon();
  });

  function endDrag(event) {
    if (dragging !== event.pointerId) return;
    dragging = null;
    splitEl.classList.remove("resizing");
    remember();
    resizeMap();
  }

  dividerEl.addEventListener("pointerup", endDrag);
  dividerEl.addEventListener("pointercancel", endDrag);

  dividerEl.addEventListener("keydown", (event) => {
    const next = keySize(event.key, current, phone(), event.shiftKey);
    if (next === null) return;
    event.preventDefault();
    setSize(next);
    remember();
    resizeMap();
  });

  win.addEventListener("resize", () => {
    current = size();
    apply();
    resizeMap();
  });

  apply();

  return {
    isOpen: () => open,
    size: () => current,
    open() {
      if (!open) setOpen(true);
    },
    close() {
      if (open) setOpen(false);
    },
  };
}

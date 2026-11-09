const DAY_MS = 24 * 60 * 60 * 1000;
const KEY_STEPS = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -30, PageUp: 30 };

export function dayNumber(iso) {
  return Math.round(Date.parse(iso) / DAY_MS);
}

export function isoFromDay(day) {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}

export function fractionForDay(day, bounds) {
  const span = bounds.max - bounds.min;
  return span === 0 ? 0 : (day - bounds.min) / span;
}

export function dayForFraction(fraction, bounds) {
  return bounds.min + Math.round(clamp(fraction, 0, 1) * (bounds.max - bounds.min));
}

export function moveHandle(selection, handle, day, bounds) {
  if (handle === "from") {
    return { from: clamp(day, bounds.min, selection.to), to: selection.to };
  }
  return { from: selection.from, to: clamp(day, selection.from, bounds.max) };
}

export function moveWindow(selection, delta, bounds) {
  const shift = clamp(delta, bounds.min - selection.from, bounds.max - selection.to);
  return { from: selection.from + shift, to: selection.to + shift };
}

// Stacked handles can only be told apart by the direction of the drag.
export function resolveHandle(handle, selection, delta) {
  if (selection.from !== selection.to || delta === 0) {
    return handle;
  }
  return delta < 0 ? "from" : "to";
}

export function selectionToPeriod(selection, bounds) {
  return {
    from: selection.from <= bounds.min ? null : isoFromDay(selection.from),
    to: selection.to >= bounds.max ? null : isoFromDay(selection.to),
  };
}

// The selection for a { from, to } period of ISO dates: a missing end opens on the bound,
// values are clamped to the bounds and a reversed pair is swapped.
export function periodSelection(from, to, bounds) {
  const first = from ? clamp(dayNumber(from), bounds.min, bounds.max) : bounds.min;
  const last = to ? clamp(dayNumber(to), bounds.min, bounds.max) : bounds.max;
  return { from: Math.min(first, last), to: Math.max(first, last) };
}

export function growSelection(selection, oldBounds, newBounds) {
  return {
    from: selection.from <= oldBounds.min ? newBounds.min : selection.from,
    to: selection.to >= oldBounds.max ? newBounds.max : selection.to,
  };
}

export function yearTicks(bounds) {
  const ticks = [];
  const first = Number(isoFromDay(bounds.min).slice(0, 4));
  const last = Number(isoFromDay(bounds.max).slice(0, 4));
  for (let year = first; year <= last; year++) {
    const day = dayNumber(`${year}-01-01`);
    if (day > bounds.min && day < bounds.max) {
      ticks.push({ year, fraction: fractionForDay(day, bounds) });
    }
  }
  return ticks;
}

// Binds the pure logic above to the slider's elements. `onChange` gets a
// { from, to } period of ISO dates, null where the selection is open-ended,
// at most once per animation frame during a drag.
export function initPeriodSlider({ trackEl, windowEl, fromHandleEl, toHandleEl, ticksEl, labelEl, resetEl, onChange }) {
  let bounds = null;
  let selection = null;
  let drag = null;
  let frame = null;
  let pending = null;

  function render() {
    const left = fractionForDay(selection.from, bounds) * 100;
    const right = fractionForDay(selection.to, bounds) * 100;
    windowEl.style.left = `${left}%`;
    windowEl.style.width = `${right - left}%`;
    fromHandleEl.style.left = `${left}%`;
    toHandleEl.style.left = `${right}%`;
    for (const [el, value, name] of [
      [fromHandleEl, selection.from, "Begin van de periode"],
      [toHandleEl, selection.to, "Einde van de periode"],
    ]) {
      el.setAttribute("aria-label", name);
      el.setAttribute("aria-valuemin", bounds.min);
      el.setAttribute("aria-valuemax", bounds.max);
      el.setAttribute("aria-valuenow", value);
      el.setAttribute("aria-valuetext", isoFromDay(value));
    }
    labelEl.textContent = `${isoFromDay(selection.from)} t/m ${isoFromDay(selection.to)}`;
    resetEl.disabled = selection.from === bounds.min && selection.to === bounds.max;
  }

  function notify() {
    if (frame === null) {
      frame = requestAnimationFrame(() => {
        frame = null;
        onChange(selectionToPeriod(selection, bounds));
      });
    }
  }

  function update(next) {
    selection = next;
    render();
    notify();
  }

  function pointerFraction(event) {
    const rect = trackEl.getBoundingClientRect();
    return (event.clientX - rect.left) / rect.width;
  }

  function startDrag(event, part) {
    if (bounds === null) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag = { part, startDay: dayForFraction(pointerFraction(event), bounds), startSelection: selection };
  }

  function onDragMove(event) {
    if (drag === null) {
      return;
    }
    const day = dayForFraction(pointerFraction(event), bounds);
    if (drag.part === "window") {
      update(moveWindow(drag.startSelection, day - drag.startDay, bounds));
      return;
    }
    drag.part = resolveHandle(drag.part, selection, day - selection.from);
    update(moveHandle(selection, drag.part, day, bounds));
  }

  function endDrag() {
    drag = null;
  }

  for (const [el, part] of [[fromHandleEl, "from"], [toHandleEl, "to"], [windowEl, "window"]]) {
    el.addEventListener("pointerdown", (event) => startDrag(event, part));
    el.addEventListener("pointermove", onDragMove);
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
  }

  // A press on the bare track moves the nearest handle there and keeps dragging it.
  trackEl.addEventListener("pointerdown", (event) => {
    if (bounds === null) {
      return;
    }
    const day = dayForFraction(pointerFraction(event), bounds);
    const part = Math.abs(day - selection.from) <= Math.abs(day - selection.to) ? "from" : "to";
    startDrag(event, part);
    update(moveHandle(selection, part, day, bounds));
  });
  trackEl.addEventListener("pointermove", onDragMove);
  trackEl.addEventListener("pointerup", endDrag);
  trackEl.addEventListener("pointercancel", endDrag);

  for (const [el, part] of [[fromHandleEl, "from"], [toHandleEl, "to"]]) {
    el.addEventListener("keydown", (event) => {
      const step = KEY_STEPS[event.key];
      if (step === undefined || bounds === null) {
        return;
      }
      event.preventDefault();
      const current = part === "from" ? selection.from : selection.to;
      update(moveHandle(selection, part, current + step, bounds));
    });
  }

  resetEl.addEventListener("click", () => {
    if (bounds !== null) {
      update({ from: bounds.min, to: bounds.max });
    }
  });

  return {
    // Sets the period, as when restoring a URL. Before the bounds are known it is kept and
    // applied when they arrive.
    setPeriod(from, to) {
      if (bounds === null) {
        pending = { from, to };
        return;
      }
      update(periodSelection(from, to, bounds));
    },
    setBounds(history) {
      const next = { min: dayNumber(history.min), max: dayNumber(history.max) };
      if (bounds !== null && pending === null && next.min === bounds.min && next.max === bounds.max) return;
      selection = selection === null ? { from: next.min, to: next.max } : growSelection(selection, bounds, next);
      bounds = next;
      if (pending !== null) {
        selection = periodSelection(pending.from, pending.to, bounds);
        pending = null;
        notify();
      }
      ticksEl.replaceChildren(
        ...yearTicks(bounds).map(({ year, fraction }) => {
          const tick = document.createElement("span");
          tick.className = "slider-tick";
          tick.style.left = `${fraction * 100}%`;
          tick.textContent = year;
          return tick;
        }),
      );
      render();
    },
  };
}

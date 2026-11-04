import { test } from "node:test";
import assert from "node:assert/strict";

import { initTimeline, sliderValueForDate } from "../js/timeline.js";

test("sliderValueForDate is zero for the range minimum", () => {
  const min = new Date(Date.UTC(1940, 5, 1));
  assert.equal(sliderValueForDate(min, min), 0);
});

test("sliderValueForDate keeps the same date after the range starts earlier", () => {
  const date = new Date(Date.UTC(1940, 5, 10));
  const before = sliderValueForDate(new Date(Date.UTC(1940, 5, 1)), date);
  const after = sliderValueForDate(new Date(Date.UTC(1940, 4, 1)), date);
  assert.equal(before, 9);
  assert.equal(after, 40);
});

function fakeElements() {
  const listeners = {};
  const el = () => ({ textContent: "", value: "0", min: "", max: "", addEventListener() {} });
  return { sliderEl: el(), playPauseEl: el(), dateDisplayEl: el(), listeners };
}

test("setRange keeps the selected date when the range starts earlier", () => {
  const els = fakeElements();
  const emitted = [];
  const timeline = initTimeline({
    ...els,
    minDate: new Date(Date.UTC(1940, 5, 1)),
    maxDate: new Date(Date.UTC(1940, 6, 1)),
    onDateChange: (date) => emitted.push(date),
  });
  els.sliderEl.value = "9";
  emitted.length = 0;

  timeline.setRange(new Date(Date.UTC(1940, 4, 1)), new Date(Date.UTC(1940, 6, 1)));

  assert.equal(els.sliderEl.value, "40");
  assert.equal(els.sliderEl.max, "61");
  assert.equal(els.dateDisplayEl.textContent, "1940-06-10");
  assert.equal(emitted.length, 0);
});

test("setRange moves to the nearest end and emits when the date falls outside the range", () => {
  const els = fakeElements();
  const emitted = [];
  const timeline = initTimeline({
    ...els,
    minDate: new Date(Date.UTC(1940, 5, 1)),
    maxDate: new Date(Date.UTC(1940, 6, 1)),
    onDateChange: (date) => emitted.push(date),
  });
  els.sliderEl.value = "9";
  emitted.length = 0;

  timeline.setRange(new Date(Date.UTC(1940, 5, 20)), new Date(Date.UTC(1940, 6, 1)));

  assert.equal(els.sliderEl.value, "0");
  assert.equal(emitted.length, 1);
});

test("initTimeline still returns the timeline when the first render throws", () => {
  const els = fakeElements();
  let calls = 0;
  const original = console.error;
  console.error = () => {};
  let timeline;
  try {
    timeline = initTimeline({
      ...els,
      minDate: new Date(Date.UTC(1940, 5, 1)),
      maxDate: new Date(Date.UTC(1940, 6, 1)),
      onDateChange: () => {
        calls += 1;
        if (calls === 1) throw new Error("first render broke");
      },
    });
  } finally {
    console.error = original;
  }
  assert.equal(typeof timeline.setRange, "function");
  timeline.setRange(new Date(Date.UTC(1940, 5, 1)), new Date(Date.UTC(1940, 6, 5)));
});

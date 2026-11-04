const DAY_MS = 24 * 60 * 60 * 1000;
const TICK_MS = 500;

export function sliderValueForDate(minDate, date) {
  return Math.round((date.getTime() - minDate.getTime()) / DAY_MS);
}

export function initTimeline({ sliderEl, playPauseEl, stepBackEl, stepForwardEl, dateDisplayEl, minDate, maxDate, onDateChange }) {
  let totalDays = sliderValueForDate(minDate, maxDate);
  sliderEl.min = "0";
  sliderEl.max = String(totalDays);
  sliderEl.value = "0";

  let playing = false;
  let intervalId = null;

  function dateForValue(value) {
    return new Date(minDate.getTime() + Number(value) * DAY_MS);
  }

  function formatDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function emitDate() {
    const date = dateForValue(sliderEl.value);
    dateDisplayEl.textContent = formatDate(date);
    onDateChange(date);
  }

  function stop() {
    playing = false;
    playPauseEl.textContent = "▶";
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  function play() {
    playing = true;
    playPauseEl.textContent = "⏸";
    intervalId = setInterval(() => {
      const next = Number(sliderEl.value) + 1;
      if (next > totalDays) {
        stop();
        return;
      }
      sliderEl.value = String(next);
      emitDate();
    }, TICK_MS);
  }

  sliderEl.addEventListener("input", () => {
    if (playing) {
      stop();
    }
    emitDate();
  });

  playPauseEl.addEventListener("click", () => {
    if (playing) {
      stop();
    } else {
      play();
    }
  });

  // On a phone one pixel of slider is several days; these reach every single day.
  function step(days) {
    if (playing) {
      stop();
    }
    const next = Math.min(Math.max(Number(sliderEl.value) + days, 0), totalDays);
    if (next !== Number(sliderEl.value)) {
      sliderEl.value = String(next);
      emitDate();
    }
  }

  stepBackEl?.addEventListener("click", () => step(-1));
  stepForwardEl?.addEventListener("click", () => step(1));

  function setRange(newMin, newMax) {
    const current = dateForValue(sliderEl.value);
    minDate = newMin;
    maxDate = newMax;
    totalDays = sliderValueForDate(minDate, maxDate);
    sliderEl.max = String(totalDays);
    const value = sliderValueForDate(minDate, current);
    if (value < 0 || value > totalDays) {
      sliderEl.value = String(Math.min(Math.max(value, 0), totalDays));
      emitDate();
      return;
    }
    sliderEl.value = String(value);
    dateDisplayEl.textContent = formatDate(current);
  }

  // A failing first render must not leave the caller without a timeline to update.
  try {
    emitDate();
  } catch (error) {
    console.error(error);
  }

  return { stop, setRange };
}

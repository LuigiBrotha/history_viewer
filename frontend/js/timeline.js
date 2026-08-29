const DAY_MS = 24 * 60 * 60 * 1000;
const TICK_MS = 500;

export function initTimeline({ sliderEl, playPauseEl, dateDisplayEl, minDate, maxDate, onDateChange }) {
  const totalDays = Math.round((maxDate.getTime() - minDate.getTime()) / DAY_MS);
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

  emitDate();

  return { stop };
}

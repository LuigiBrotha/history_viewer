import { fetchRoutes, fetchStatus } from "./api.js";
import { mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { rampGradient } from "./color-ramp.js";
import { initPeriodSlider } from "./period-slider.js";
import { createStatusMap, updateRoutes, setLastPatrol, setPeriod, visibleCount } from "./status-map.js";

const POLL_INTERVAL_MS = 5000;
const NO_CONNECTION = "Geen verbinding, opnieuw proberen…";
const MAP_FAILED = "Kaart kon niet laden";

function main() {
  const liveStatusEl = document.getElementById("live-status");
  let state;
  try {
    state = createStatusMap("status-map");
  } catch (error) {
    console.error(error);
    liveStatusEl.textContent = MAP_FAILED;
    return;
  }

  const countEl = document.getElementById("route-count");
  const trackEl = document.getElementById("slider-track");
  const windowEl = document.getElementById("slider-window");
  windowEl.style.background = rampGradient();

  let routes = [];
  let lastStatus = null;

  function renderStatusLine() {
    if (lastStatus !== null) {
      liveStatusEl.textContent = statusLine(lastStatus, new Date(), uncomputedLegs(routes));
    }
  }

  function renderCount() {
    const { visible, total } = visibleCount(state);
    countEl.textContent = `${visible} van ${total} routes`;
  }

  const slider = initPeriodSlider({
    trackEl,
    windowEl,
    fromHandleEl: document.getElementById("slider-from"),
    toHandleEl: document.getElementById("slider-to"),
    ticksEl: document.getElementById("slider-ticks"),
    labelEl: document.getElementById("period-label"),
    resetEl: document.getElementById("period-reset"),
    onChange: ({ from, to }) => {
      setPeriod(state, from, to);
      renderCount();
    },
  });
  renderCount();

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => {
      routes = mergeRoutes(routes, changed);
      renderStatusLine();
      updateRoutes(state, changed);
      if (state.history !== null) {
        slider.setBounds(state.history);
      }
      renderCount();
    },
    onStatus: (status) => {
      lastStatus = status;
      renderStatusLine();
      setLastPatrol(state, status.last_patrol ? status.last_patrol.external_id : null);
    },
    onError: (error) => {
      console.error(error);
      liveStatusEl.textContent = NO_CONNECTION;
    },
    setTimer: (fn, ms) => setTimeout(fn, ms),
  });
}

main();

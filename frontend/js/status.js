import { fetchRoutes, fetchStatus } from "./api.js";
import { mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { rampGradient } from "./color-ramp.js";
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

  const fromEl = document.getElementById("period-from");
  const toEl = document.getElementById("period-to");
  const resetEl = document.getElementById("period-reset");
  const countEl = document.getElementById("route-count");
  const legendStartEl = document.getElementById("legend-start");
  const legendEndEl = document.getElementById("legend-end");
  document.getElementById("legend-ramp").style.background = rampGradient();

  let routes = [];
  let lastStatus = null;

  function renderCount() {
    const { visible, total } = visibleCount(state);
    countEl.textContent = `${visible} van ${total} routes`;
    resetEl.disabled = fromEl.value === "" && toEl.value === "";
  }

  function renderHistory() {
    if (state.history !== null) {
      legendStartEl.textContent = state.history.min.slice(0, 4);
      legendEndEl.textContent = state.history.max.slice(0, 4);
      for (const el of [fromEl, toEl]) {
        el.min = state.history.min;
        el.max = state.history.max;
      }
    }
  }

  function applyPeriod() {
    setPeriod(state, fromEl.value || null, toEl.value || null);
    renderCount();
  }

  fromEl.addEventListener("change", applyPeriod);
  toEl.addEventListener("change", applyPeriod);
  resetEl.addEventListener("click", () => {
    fromEl.value = "";
    toEl.value = "";
    applyPeriod();
  });
  renderCount();

  function renderStatusLine() {
    if (lastStatus !== null) {
      liveStatusEl.textContent = statusLine(lastStatus, new Date(), uncomputedLegs(routes));
    }
  }

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => {
      routes = mergeRoutes(routes, changed);
      renderStatusLine();
      updateRoutes(state, changed);
      renderHistory();
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

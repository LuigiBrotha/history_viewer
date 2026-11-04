import { fetchRoutes, fetchStatus } from "./api.js";
import { mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { createStatusMap, updateRoutes, setLastPatrol } from "./status-map.js";

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

  let routes = [];
  let lastStatus = null;

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

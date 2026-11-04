import { fetchRoutes, fetchStatus } from "./api.js";
import { statusLine, startPolling } from "./live.js";
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

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => updateRoutes(state, changed),
    onStatus: (status) => {
      liveStatusEl.textContent = statusLine(status, new Date());
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

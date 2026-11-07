import { canEdit, fetchPlaces, fetchShips, fetchStatus } from "./api.js";
import { createShipLoader, mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { createShipLayer } from "./ship-layer.js";
import { mergeShips, shipsInPeriod } from "./ship-model.js";
import { createLoadIndicator } from "./load-indicator.js";
import { initAtlas } from "./atlas.js";
import { initBattles } from "./battles.js";
import { createMapSearch } from "./map-search.js";
import { matchBattles } from "./search-model.js";
import { createBoatPanel } from "./boat-panel.js";
import { rampGradient } from "./color-ramp.js";
import { initPeriodSlider } from "./period-slider.js";
import { createPeriodView } from "./period-view.js";
import { createUrlSync } from "./url-sync.js";
import { createStatusMap, highlightPatrol, selectBoat, updateRoutes, setLastPatrol, setPeriod, visibleCount } from "./status-map.js";

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

  const periodView = createPeriodView({
    search: location.search,
    urlSync: createUrlSync({ kind: "period" }),
    map: state.map,
  });
  if (periodView.mapPinned()) state.fitted = true;

  const shipLayer = createShipLayer(state.map, { onShipClick: (ship) => boatPanel.openShip(ship) });
  let ships = [];
  const boatPanel = createBoatPanel({
    rootEl: document.getElementById("boat-panel"),
    getShips: () => ships,
    onShowPatrol: (patrol) => highlightPatrol(state, patrol.external_id),
    onOpenBoat: (slug) => selectBoat(state, slug),
    onClose: () => selectBoat(state, null),
  });
  state.onRouteClick = (patrol) => {
    selectBoat(state, patrol.boat_slug);
    boatPanel.open(patrol.boat_slug);
  };

  function renderShips() {
    shipLayer.setShips(shipsInPeriod(ships, state.from, state.to));
  }

  const loadShips = createShipLoader({
    fetchShips,
    onShips: (changed) => {
      ships = mergeShips(ships, changed);
      renderShips();
    },
    onError: (error) => console.error(error),
  });

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

  // The map shows the situation at the end of the selection.
  let atlas = { setDate() {} };
  function renderAtlas() {
    const end = state.to ?? state.history?.max ?? null;
    if (end !== null) {
      atlas.setDate(end);
    }
  }
  initAtlas(state.map).then((loaded) => {
    atlas = loaded;
    renderAtlas();
  });

  const battles = initBattles({
    map: state.map,
    mode: "period",
    onBattleChange: periodView.onBattleChange,
    onNoposChange: periodView.onNoposChange,
  });
  battles.setPeriod(null, null);

  const search = createMapSearch({
    map: state.map,
    sources: [{ group: "Veldslagen", search: (q) => matchBattles(battles.allBattles(), q) }],
    onPick: ({ group, item }) => {
      if (group === "Plaatsen") {
        if (!battles.moveEditTo(item.lat, item.lng)) search.showPlace(item);
      } else {
        battles.selectBattle(item.title);
      }
    },
    fetchPlaces,
  });
  battles.placeToggle();

  const slider = initPeriodSlider({
    trackEl,
    windowEl,
    fromHandleEl: document.getElementById("slider-from"),
    toHandleEl: document.getElementById("slider-to"),
    ticksEl: document.getElementById("slider-ticks"),
    labelEl: document.getElementById("period-label"),
    resetEl: document.getElementById("period-reset"),
    onChange: ({ from, to }) => {
      periodView.onPeriod({ from, to });
      setPeriod(state, from, to);
      battles.setPeriod(from, to);
      renderShips();
      renderCount();
      renderAtlas();
    },
  });
  renderCount();
  periodView.restore({ slider, battles });

  const loadIndicator = createLoadIndicator(document.getElementById("load-indicator"));

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes: loadIndicator.fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => {
      try {
        routes = mergeRoutes(routes, changed);
        renderStatusLine();
        updateRoutes(state, changed);
        if (state.history !== null) {
          slider.setBounds(state.history);
        }
        renderCount();
        renderAtlas();
      } finally {
        loadIndicator.finish();
      }
    },
    onStatus: (status) => {
      loadIndicator.setTotal(status.patrol_count);
      lastStatus = status;
      battles.setEditable(canEdit(status));
      renderStatusLine();
      loadShips(status.revision);
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

import { canEdit, fetchPlaces, fetchShips, fetchStatus } from "./api.js";
import { createShipLoader, mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { createShipLayer } from "./ship-layer.js";
import { mergeShips, shipsInPeriod } from "./ship-model.js";
import { createLiberationLayer, loadLiberations } from "./liberation-layer.js";
import { liberationBattle, liberationsInPeriod } from "./liberation-model.js";
import { createLoadIndicator } from "./load-indicator.js";
import { initAtlas } from "./atlas.js";
import { initBattles } from "./battles.js";
import { createMapSearch } from "./map-search.js";
import { createShortcutHelp } from "./shortcut-help.js";
import { installShortcuts, pageActions } from "./shortcuts.js";
import { matchBattles } from "./search-model.js";
import { searchLabels } from "./battle-labels.js";
import { createSubjects } from "./subjects.js";
import { rampGradient } from "./color-ramp.js";
import { initPeriodSlider } from "./period-slider.js";
import { createPeriodView } from "./period-view.js";
import { createUrlSync } from "./url-sync.js";
import { createBoatToggle, createNamesToggle, createOthersToggle, createShipsToggle, createLiberationsToggle } from "./map-toggle.js";
import { readView } from "./url-state.js";
import { createStatusMap, fitAllRoutes, fitBoat, highlightPatrol, setHistory, selectBoat, updateRoutes, setLastPatrol, setBoatsVisible, setPeriod, visibleCount } from "./status-map.js";

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

  const loadIndicator = createLoadIndicator(document.getElementById("load-indicator"));
  const urlSync = createUrlSync({ kind: "period" });
  const periodView = createPeriodView({
    search: location.search,
    urlSync,
    map: state.map,
  });
  if (periodView.mapPinned()) state.fitted = true;

  const shipLayer = createShipLayer(state.map, { onShipClick: (ship) => subjects.openShip(ship) });
  // A liberation that was part of a Veldslag opens it, as the list does.
  const liberationLayer = createLiberationLayer(state.map, {
    onLiberationClick: (liberation) => {
      const title = liberationBattle(liberation, battles.allBattles());
      if (title !== null) battles.selectBattle(title, { pickDate: true });
    },
  });
  let liberations = [];

  function renderLiberations() {
    liberationLayer.setLiberations(liberationsInPeriod(liberations, state.from, state.to));
  }

  // Once, after the first routes: the map works without them.
  loadIndicator.firstDrawn
    .then(() => loadLiberations())
    .then((loaded) => {
      liberations = loaded;
      renderLiberations();
    })
    .catch((error) => console.error(error));
  let ships = [];
  state.onRouteClick = (patrol) => subjects.openBoat(patrol.boat_slug);

  function renderShips() {
    shipLayer.setShips(shipsInPeriod(ships, state.from, state.to));
  }

  const loadShips = createShipLoader({
    fetchShips,
    onShips: (changed) => {
      ships = mergeShips(ships, changed);
      subjects.setShips(ships);
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
    startAfter: loadIndicator.firstDrawn,
  });
  battles.setPeriod(null, null);

  const subjects = createSubjects({
    battles,
    urlSync,
    getShips: () => ships,
    ready: loadIndicator.firstDrawn,
    hooks: {
      follow(slug, { fromList }) {
        selectBoat(state, slug);
        if (fromList) fitBoat(state, slug);
      },
      stopFollow: () => selectBoat(state, null),
      followed: () => state.selectedSlug,
      showShip(hit, { fromList }) {
        if (fromList && hit.lat != null && hit.lng != null) state.map.setView([hit.lat, hit.lng], Math.max(state.map.getZoom(), 6));
      },
      showPatrol(patrol) {
        boatToggle.show();
        highlightPatrol(state, patrol.external_id);
      },
    },
  });

  const search = createMapSearch({
    map: state.map,
    sources: [
      { group: "Veldslagen", search: (q) => matchBattles(battles.allBattles(), q) },
      { group: "Filters", search: (q) => searchLabels(battles.allBattles(), q) },
    ],
    onPick: ({ group, item }) => {
      if (group === "Plaatsen") {
        if (!battles.moveEditTo(item.lat, item.lng)) search.showPlace(item);
      } else if (group === "Filters") {
        battles.addLabel(item);
      } else {
        battles.selectBattle(item.title);
      }
    },
    fetchPlaces,
  });
  battles.placeToggle();
  createNamesToggle({ map: state.map, battles, urlSync, shown: !readView(location.search, "period").namesOff });
  createOthersToggle({ map: state.map, battles, urlSync, shown: !readView(location.search, "period").othersOff });
  const boatToggle = createBoatToggle({
    map: state.map,
    visible: !readView(location.search, "period").boatsOff,
    onChange: (visible) => {
      setBoatsVisible(state, visible);
      urlSync.update({ boatsOff: visible ? null : true });
    },
  });
  createShipsToggle({ map: state.map, shipLayer, urlSync, shown: !readView(location.search, "period").shipsOff });
  createLiberationsToggle({ map: state.map, liberationLayer, urlSync, shown: !readView(location.search, "period").liberationsOff });
  installShortcuts({ actions: pageActions({ battles: () => battles, search: () => search, help: createShortcutHelp() }) });

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
      subjects.setPeriod(from, to);
      renderShips();
      renderLiberations();
      renderCount();
      renderAtlas();
    },
  });
  renderCount();
  periodView.restore({ slider, battles });
  const restored = readView(location.search, "period");
  if (restored.boat !== undefined) subjects.openBoat(restored.boat);
  if (restored.ship !== undefined) subjects.restoreShip(restored.ship);

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes: loadIndicator.fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => {
      try {
        routes = mergeRoutes(routes, changed);
        subjects.setRoutes(routes);
        renderStatusLine();
        updateRoutes(state, changed);
        renderCount();
        renderAtlas();
        if (loadIndicator.complete()) fitAllRoutes(state);
      } finally {
        loadIndicator.finish();
      }
    },
    onStatus: (status) => {
      loadIndicator.setTotal(status.patrol_count);
      lastStatus = status;
      if (status.first_departure) {
        const history = { min: status.first_departure, max: status.last_departure };
        setHistory(state, history);
        slider.setBounds(history);
        renderAtlas();
      }
      battles.setEditable(canEdit(status));
      renderStatusLine();
      loadIndicator.firstDrawn.then(() => loadShips(status.revision));
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

import { canEdit, excludePoint, fetchBoats, fetchRoutes, fetchShips, fetchStatus, restorePoint } from "./api.js";
import { activeBoatsOnDate, dateRange, followView, notOnPatrolMessage } from "./time-model.js";
import { initAtlas } from "./atlas.js";
import { createMap, renderActiveBoats, renderFollowedRoute, clearFollowedRoute } from "./map.js";
import { initTimeline } from "./timeline.js";
import { boatsHeading, renderBoatList, renderExcludedPoints, renderShipSummary, updateDateLabel } from "./sidebar.js";
import { createShipLoader, mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { createShipLayer } from "./ship-layer.js";
import { mergeShips, shipsUpToDate } from "./ship-model.js";

const COLLAPSED_BY_DEFAULT_QUERY = "(max-width: 699px)";
const POLL_INTERVAL_MS = 5000;
const NO_DATED_POINTS = "Geen gedateerde routepunten beschikbaar.";
const NO_CONNECTION = "Geen verbinding, opnieuw proberen…";
const MAP_FAILED = "Kaart kon niet laden";

function main() {
  const sliderEl = document.getElementById("date-slider");
  const playPauseEl = document.getElementById("play-pause");
  const dateDisplayEl = document.getElementById("date-display");
  const labelEl = document.getElementById("boat-date-label");
  const listEl = document.getElementById("boat-list");
  const followStatusEl = document.getElementById("follow-status");
  const liveStatusEl = document.getElementById("live-status");
  const excludedEl = document.getElementById("excluded-points");
  const resetButton = document.getElementById("reset-follow");
  const toggleBoatsButton = document.getElementById("toggle-boats");
  const boatsHeadingEl = document.getElementById("boats-heading");
  const sidebarEl = document.getElementById("sidebar");
  const shipTotalsEl = document.getElementById("ship-totals");
  const shipUnknownEl = document.getElementById("ship-unknown");

  if (typeof L === "undefined") {
    liveStatusEl.textContent = MAP_FAILED;
    return;
  }

  let routes = [];
  let routesBySlug = new Map();
  let boatsBySlug = new Map();
  let mapState = null;
  let timeline = null;
  let followedSlug = null;
  let currentDate = null;
  let atlas = { setDate() {} };
  let ships = [];
  let shipLayer = null;
  let editable = false;

  // fit is true for user actions; live updates redraw without touching the view.
  function render(date, fit) {
    currentDate = date;
    const active = activeBoatsOnDate(routes, date);
    updateDateLabel(labelEl, date);
    atlas.setDate(date.toISOString().slice(0, 10));

    followStatusEl.textContent = "";

    if (followedSlug !== null) {
      const boatRoutes = routesBySlug.get(followedSlug);
      const view = followView(boatRoutes, date);
      renderActiveBoats(mapState, [], onBoatSelect);
      renderFollowedRoute(mapState, view.patrol, view.position, {
        fit,
        onExclude: editable ? (point, button) => editPoint(excludePoint, "Uitsluiten mislukt", view.patrol, point, button) : null,
      });
      renderExcludedPoints({
        listEl: excludedEl,
        patrol: view.patrol,
        onRestore: editable ? (point, button) => editPoint(restorePoint, "Herstellen mislukt", view.patrol, point, button) : null,
      });
      if (view.position === null) {
        followStatusEl.textContent = notOnPatrolMessage(boatRoutes[0].boat_number, date);
      }
    } else {
      clearFollowedRoute(mapState);
      renderExcludedPoints({ listEl: excludedEl, patrol: null, onRestore: null });
      renderActiveBoats(mapState, active, onBoatSelect);
    }

    renderShips(date);

    boatsHeadingEl.textContent = boatsHeading(active.length);
    renderBoatList({ listEl, activeBoats: active, followedSlug, onBoatSelect, boatsBySlug });
  }

  function renderShips(date) {
    if (shipLayer === null) return;
    const visible = shipsUpToDate(ships, date, followedSlug);
    shipLayer.setShips(visible);
    renderShipSummary({ totalsEl: shipTotalsEl, unknownEl: shipUnknownEl }, visible, followedSlug !== null);
  }

  const loadShips = createShipLoader({
    fetchShips,
    onShips: (changed) => {
      ships = mergeShips(ships, changed);
      if (currentDate !== null) {
        renderShips(currentDate);
      }
    },
    onError: (error) => console.error(error),
  });

  // Date, followed boat and zoom stay as they are: the returned patrol replaces
  // the old one and the view is redrawn without fitting.
  async function editPoint(request, failure, patrol, point, button) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "Bezig…";
    try {
      const updated = await request(patrol.external_id, point.sequence);
      mapState.map.closePopup();
      onData([updated]);
    } catch (error) {
      console.error(error);
      followStatusEl.textContent = error.message || failure;
      button.disabled = false;
      button.textContent = label;
    }
  }

  function onBoatSelect(slug) {
    followedSlug = slug;
    clearFollowedRoute(mapState);
    resetButton.hidden = false;
    render(currentDate, true);
  }

  resetButton.addEventListener("click", () => {
    followedSlug = null;
    resetButton.hidden = true;
    clearFollowedRoute(mapState);
    render(currentDate, true);
  });

  function setBoatsCollapsed(collapsed) {
    sidebarEl.classList.toggle("collapsed", collapsed);
    toggleBoatsButton.setAttribute("aria-expanded", String(!collapsed));
  }

  // On a phone the list would cover the map, so it starts collapsed there.
  setBoatsCollapsed(window.matchMedia(COLLAPSED_BY_DEFAULT_QUERY).matches);

  toggleBoatsButton.addEventListener("click", () => {
    setBoatsCollapsed(!sidebarEl.classList.contains("collapsed"));
  });

  async function refreshBoats() {
    try {
      const boats = await fetchBoats();
      boatsBySlug = new Map(boats.map((boat) => [boat.slug, boat]));
      if (currentDate !== null) {
        render(currentDate, false);
      }
    } catch (error) {
      console.error(error);
    }
  }

  let lastStatus = null;

  function renderStatusLine() {
    if (lastStatus !== null) {
      liveStatusEl.textContent = statusLine(lastStatus, new Date(), uncomputedLegs(routes));
    }
  }

  function onData(changed) {
    routes = mergeRoutes(routes, changed);
    renderStatusLine();
    routesBySlug = new Map();
    for (const patrol of routes) {
      if (!routesBySlug.has(patrol.boat_slug)) {
        routesBySlug.set(patrol.boat_slug, []);
      }
      routesBySlug.get(patrol.boat_slug).push(patrol);
    }

    const range = dateRange(routes);
    if (range === null) {
      labelEl.textContent = NO_DATED_POINTS;
    } else if (timeline === null) {
      if (mapState === null) {
        mapState = createMap("map");
        shipLayer = createShipLayer(mapState.map);
        initAtlas(mapState.map).then((loaded) => {
          atlas = loaded;
          atlas.setDate(currentDate.toISOString().slice(0, 10));
        });
      }
      currentDate = range.min;
      timeline = initTimeline({
        sliderEl,
        playPauseEl,
        dateDisplayEl,
        minDate: range.min,
        maxDate: range.max,
        onDateChange: (date) => render(date, true),
      });
    } else {
      timeline.setRange(range.min, range.max);
      render(currentDate, false);
    }

    // New boats bring new type labels.
    refreshBoats();
  }

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes,
    isHidden: () => document.hidden,
    onData,
    onStatus: (status) => {
      lastStatus = status;
      const wasEditable = editable;
      editable = canEdit(status);
      if (editable !== wasEditable && currentDate !== null) {
        render(currentDate, false);
      }
      renderStatusLine();
      loadShips(status.revision);
    },
    onError: (error) => {
      console.error(error);
      liveStatusEl.textContent = NO_CONNECTION;
    },
    setTimer: (fn, ms) => setTimeout(fn, ms),
  });
}

main();

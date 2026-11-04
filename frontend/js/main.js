import { fetchBoats, fetchRoutes, fetchStatus } from "./api.js";
import { activeBoatsOnDate, dateRange, followView, notOnPatrolMessage } from "./time-model.js";
import { createMap, renderActiveBoats, renderFollowedRoute, clearFollowedRoute } from "./map.js";
import { initTimeline } from "./timeline.js";
import { renderBoatList, updateDateLabel } from "./sidebar.js";
import { mergeRoutes, statusLine, startPolling } from "./live.js";

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
  const resetButton = document.getElementById("reset-follow");
  const toggleSidebarButton = document.getElementById("toggle-sidebar");
  const sidebarEl = document.getElementById("sidebar");

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

  // fit is true for user actions; live updates redraw without touching the view.
  function render(date, fit) {
    currentDate = date;
    const active = activeBoatsOnDate(routes, date);
    updateDateLabel(labelEl, date);

    followStatusEl.textContent = "";

    if (followedSlug !== null) {
      const boatRoutes = routesBySlug.get(followedSlug);
      const view = followView(boatRoutes, date);
      renderActiveBoats(mapState, [], onBoatSelect);
      renderFollowedRoute(mapState, view.patrol, view.position, { fit });
      if (view.position === null) {
        followStatusEl.textContent = notOnPatrolMessage(boatRoutes[0].boat_number, date);
      }
    } else {
      clearFollowedRoute(mapState);
      renderActiveBoats(mapState, active, onBoatSelect);
    }

    renderBoatList({ listEl, activeBoats: active, followedSlug, onBoatSelect, boatsBySlug });
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

  toggleSidebarButton.addEventListener("click", () => {
    sidebarEl.classList.toggle("collapsed");
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

  function onData(changed) {
    routes = mergeRoutes(routes, changed);
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
      liveStatusEl.textContent = statusLine(status, new Date());
    },
    onError: (error) => {
      console.error(error);
      liveStatusEl.textContent = NO_CONNECTION;
    },
    setTimer: (fn, ms) => setTimeout(fn, ms),
  });
}

main();

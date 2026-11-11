import { EditError, canEdit, excludePoint, fetchBoats, fetchPlaces, fetchShips, fetchStatus, restorePoint } from "./api.js";
import { activeBoatsOnDate, dateRange, followView, notOnPatrolMessage, parseDate } from "./time-model.js";
import { createLoadIndicator } from "./load-indicator.js";
import { initAtlas } from "./atlas.js";
import { initBattles } from "./battles.js";
import { createSubjects } from "./subjects.js";
import { firstPatrolDate } from "./subject-model.js";
import { createMapSearch } from "./map-search.js";
import { createShortcutHelp } from "./shortcut-help.js";
import { installShortcuts, pageActions } from "./shortcuts.js";
import { matchBattles, matchBoats, matchShips } from "./search-model.js";
import { searchLabels } from "./battle-labels.js";
import { restoreLabels } from "./period-view.js";
import { createMap, renderActiveBoats, renderFollowedRoute, clearFollowedRoute, setBoatsVisible, setRoutesVisible } from "./map.js";
import { createBoatToggle, createNamesToggle, createOthersToggle, createRouteToggle, createShipsToggle, createLiberationsToggle } from "./map-toggle.js";
import {
  beginEdit,
  clearEditError,
  createEditState,
  failEdit,
  finishEdit,
  followStatusText,
  followedRouteChanged,
  isBusy,
} from "./edit-state.js";
import { initTimeline } from "./timeline.js";
import { readView } from "./url-state.js";
import { createUrlSync } from "./url-sync.js";
import { boatsHeading, renderExcludedPoints, renderShipSummary, updateDateLabel } from "./sidebar.js";
import { createShipLoader, mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { createShipLayer } from "./ship-layer.js";
import { mergeShips, shipsUpToDate } from "./ship-model.js";
import { createLiberationLayer, loadLiberations } from "./liberation-layer.js";
import { liberationBattle, liberationPlaces, liberationsOnDate } from "./liberation-model.js";

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

  // The URL is read once, before the first write can replace it.
  const initialView = readView(location.search, "date");
  const urlSync = createUrlSync({ kind: "date" });
  // While the URL's view is restored, the follow fit stays off so the pinned Kaartuitsnede wins.
  let restoring = false;
  let pinnedMap = null;
  let pinnedBattle = null;

  let routes = [];
  let routesBySlug = new Map();
  let boatsBySlug = new Map();
  let mapState = null;
  let timeline = null;
  let followedSlug = null;
  let currentDate = null;
  let atlas = { setDate() {} };
  let battles = { setDate() {}, setEditable() {}, allBattles: () => [] };
  let mapSearch = null;
  let subjects = null;
  // A boat chosen before its patrols have arrived: { slug, fromList, restored }.
  let pendingFollow = null;
  let lastDeparture = null;
  let routeToggle = null;
  installShortcuts({ actions: pageActions({ battles: () => battles, search: () => mapSearch, help: createShortcutHelp() }) });
  let ships = [];
  let shipLayer = null;
  let liberationLayer = null;
  let places = [];
  let editable = false;
  // Edit errors and in-flight requests outlive every redraw.
  const editState = createEditState();
  // What the followed route layer shows now, or null when it is empty.
  let drawnRoute = null;

  // fit is true for user actions; live updates redraw without touching the view.
  function render(date, fit) {
    currentDate = date;
    urlSync.update({ date: date.toISOString().slice(0, 10) });
    const active = activeBoatsOnDate(routes, date);
    updateDateLabel(labelEl, date);
    atlas.setDate(date.toISOString().slice(0, 10));
    battles.setDate(date.toISOString().slice(0, 10));

    let notOnPatrol = "";

    if (followedSlug !== null) {
      const boatRoutes = routesBySlug.get(followedSlug);
      const view = followView(boatRoutes, date);
      renderActiveBoats(mapState, [], onBoatSelect);
      // A poll that changed nothing here must not redraw: that would close an open popup.
      const next = { patrol: view.patrol, position: view.position, editable };
      if (followedRouteChanged(drawnRoute, next)) {
        renderFollowedRoute(mapState, view.patrol, view.position, {
          fit: fit && !restoring,
          onExclude: editable ? (point, button) => editPoint(excludePoint, "Uitsluiten mislukt", view.patrol, point, button) : null,
          isBusy: (point) => view.patrol !== null && isBusy(editState, view.patrol.external_id, point.sequence),
        });
        drawnRoute = next;
      }
      renderExcludedPoints({
        listEl: excludedEl,
        patrol: view.patrol,
        onRestore: editable ? (point, button) => editPoint(restorePoint, "Herstellen mislukt", view.patrol, point, button) : null,
        isBusy: (externalId, sequence) => isBusy(editState, externalId, sequence),
      });
      if (view.position === null) {
        notOnPatrol = notOnPatrolMessage(boatRoutes[0].boat_number, date);
      }
    } else {
      clearDrawnRoute();
      renderExcludedPoints({ listEl: excludedEl, patrol: null, onRestore: null });
      renderActiveBoats(mapState, active, onBoatSelect);
    }

    followStatusEl.textContent = followStatusText(notOnPatrol, editState.error);

    renderShips(date);
    renderLiberations(date);

    boatsHeadingEl.textContent = boatsHeading(active.length);
    subjects?.setDate(date.toISOString().slice(0, 10), new Set(active.map((boat) => boat.boatSlug)));
  }

  function renderShips(date) {
    if (shipLayer === null) return;
    const visible = shipsUpToDate(ships, date, followedSlug);
    shipLayer.setShips(visible);
    renderShipSummary({ totalsEl: shipTotalsEl, unknownEl: shipUnknownEl }, visible, followedSlug !== null);
  }

  function renderLiberations(date) {
    liberationLayer?.setLiberations(liberationsOnDate(places, date.toISOString().slice(0, 10)));
  }

  // A liberation that was part of a Veldslag opens it, as the list does.
  function onLiberationClick(liberation) {
    const title = liberationBattle(liberation, battles.allBattles());
    if (title !== null) battles.selectBattle(title, { pickDate: true });
  }

  const loadShips = createShipLoader({
    fetchShips,
    onShips: (changed) => {
      ships = mergeShips(ships, changed);
      subjects?.setShips(ships);
      if (currentDate !== null) {
        renderShips(currentDate);
      }
    },
    onError: (error) => console.error(error),
  });

  function clearDrawnRoute() {
    clearFollowedRoute(mapState);
    drawnRoute = null;
  }

  // Date, followed boat and zoom stay as they are: the returned patrol replaces
  // the old one and the view is redrawn without fitting. A failure stays in
  // editState until the next edit, so polls cannot wipe it.
  async function editPoint(request, failure, patrol, point, button) {
    if (!beginEdit(editState, patrol.external_id, point.sequence)) {
      return;
    }
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "Bezig…";
    let updated;
    try {
      updated = await request(patrol.external_id, point.sequence);
    } catch (error) {
      console.error(error);
      // Only our own Dutch messages reach the user; the rest is in the console.
      failEdit(editState, patrol.external_id, point.sequence, error instanceof EditError ? error.message : failure);
      button.disabled = false;
      button.textContent = label;
      // A popup rebuilt while the request ran still says Bezig…: force a redraw.
      drawnRoute = null;
      render(currentDate, false);
      return;
    }
    finishEdit(editState, patrol.external_id, point.sequence);
    onData([updated]);
  }

  // What choosing an Onderwerp does on this page's map (see subjects.js).
  const subjectHooks = {
    follow(slug, { fromList }) {
      const boatRoutes = routesBySlug.get(slug);
      if (boatRoutes === undefined) {
        stopFollowing();
        if (!loadIndicator.complete()) pendingFollow = { slug, fromList, restored: restoring };
        return;
      }
      pendingFollow = null;
      if (fromList && !activeBoatsOnDate(routes, currentDate).some((boat) => boat.boatSlug === slug)) {
        const first = firstPatrolDate(boatRoutes);
        if (first !== null) timeline?.setDate(parseDate(first));
      }
      followBoat(slug);
    },
    stopFollow: stopFollowing,
    followed: () => followedSlug ?? pendingFollow?.slug ?? null,
    showShip(hit, { fromList }) {
      if (!fromList) return;
      if (hit.date) timeline?.setDate(parseDate(hit.date));
      if (hit.lat != null && hit.lng != null) mapState.map.setView([hit.lat, hit.lng], Math.max(mapState.map.getZoom(), 6));
    },
    showPatrol(patrol, boat) {
      routeToggle?.show();
      followBoat(boat.slug);
      timeline?.setDate(parseDate(patrol.departure_date));
    },
  };

  function stopFollowing() {
    pendingFollow = null;
    if (followedSlug === null) return;
    followedSlug = null;
    urlSync.update({ boat: null });
    resetButton.hidden = true;
    clearEditError(editState);
    clearDrawnRoute();
    render(currentDate, true);
  }

  function followBoat(slug) {
    followedSlug = slug;
    urlSync.update({ boat: slug });
    clearEditError(editState);
    clearDrawnRoute();
    resetButton.hidden = false;
    render(currentDate, true);
  }

  // Choosing a result does what clicking that thing does.
  function initSearch(map) {
    const search = createMapSearch({
      map,
      sources: [
        { group: "Boten", search: (q) => matchBoats([...boatsBySlug.values()], q) },
        { group: "Schepen", search: (q) => matchShips(ships, q) },
        { group: "Veldslagen", search: (q) => matchBattles(battles.allBattles(), q) },
        { group: "Filters", search: (q) => searchLabels(battles.allBattles(), q) },
      ],
      onPick: ({ group, item }) => {
        if (group === "Boten") {
          subjects.openBoat(item.slug, { fromList: true });
        } else if (group === "Schepen") {
          subjects.openShip(item, { fromList: true });
        } else if (group === "Veldslagen") {
          battles.selectBattle(item.title);
        } else if (group === "Filters") {
          battles.addLabel(item);
        } else if (!battles.moveEditTo(item.lat, item.lng)) {
          search.showPlace(item);
        }
      },
      fetchPlaces,
    });
    battles.placeToggle();
    mapSearch = search;
  }

  function onBoatSelect(slug) {
    subjects.openBoat(slug);
  }

  // The boat is followed for as long as the Artikel is open.
  resetButton.addEventListener("click", () => battles.closeArticle());

  // Showing a battle moves the map, so the pinned Kaartuitsnede is applied again once it shows.
  function onBattleChange(title) {
    urlSync.update({ battle: title });
    if (pinnedMap !== null && title === pinnedBattle) {
      applyPinnedMap();
    }
  }

  // The deferred selection has an answer: an unknown title leaves the URL, and the pin ends.
  function endPinnedBattle(found) {
    if (!found) urlSync.update({ battle: null });
    pinnedBattle = null;
    pinnedMap = null;
  }

  function applyPinnedMap() {
    const { lat, lng, zoom } = pinnedMap;
    pinnedMap = null;
    mapState.map.setView([lat, lng], zoom, { animate: false });
  }

  // Each value of the URL was validated on its own, so each is restored on its own.
  function restoreView() {
    restoring = true;
    try {
      if (initialView.boat !== undefined) {
        subjects.openBoat(initialView.boat);
      }
      if (initialView.ship !== undefined) {
        subjects.restoreShip(initialView.ship);
      }
      if (initialView.date !== undefined) {
        timeline.setDate(parseDate(initialView.date));
      }
      if (initialView.nopos) {
        urlSync.update({ nopos: true });
        battles.setOnlyWithoutPosition(true);
      }
      restoreLabels(initialView, urlSync, battles);
      if (initialView.battle !== undefined) {
        pinnedBattle = initialView.battle;
        pinnedMap = initialView.map ?? null;
        // Kept in the URL until the battles have loaded and know the title.
        urlSync.update({ battle: initialView.battle });
        battles.selectBattle(initialView.battle, { onResolved: endPinnedBattle });
      }
    } finally {
      restoring = false;
    }
    if (initialView.map !== undefined) {
      const { lat, lng, zoom } = initialView.map;
      mapState.map.setView([lat, lng], zoom, { animate: false });
    }
  }

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
        shipLayer = createShipLayer(mapState.map, { onShipClick: (ship) => subjects.openShip(ship) });
        liberationLayer = createLiberationLayer(mapState.map, { onLiberationClick });
        battles = initBattles({
          map: mapState.map,
          mode: "date",
          onPickDate: (iso) => timeline?.setDate(parseDate(iso)),
          onBattleChange,
          onNoposChange: (on) => urlSync.update({ nopos: on || null }),
        });
        subjects = createSubjects({ battles, urlSync, getShips: () => ships, hooks: subjectHooks, ready: loadIndicator.firstDrawn });
        subjects.setShips(ships);
        mapState.map.on("moveend", () => {
          const center = mapState.map.getCenter();
          urlSync.update({ map: { lat: center.lat, lng: center.lng, zoom: mapState.map.getZoom() } });
        });
        battles.setEditable(editable);
        initSearch(mapState.map);
        createNamesToggle({ map: mapState.map, battles, urlSync, shown: !initialView.namesOff });
        createOthersToggle({ map: mapState.map, battles, urlSync, shown: !initialView.othersOff });
        routeToggle = createRouteToggle({
          map: mapState.map,
          visible: !initialView.routesOff,
          onChange: (visible) => {
            setRoutesVisible(mapState, visible);
            urlSync.update({ routesOff: visible ? null : true });
          },
        });
        createBoatToggle({
          map: mapState.map,
          visible: !initialView.boatsOff,
          onChange: (visible) => {
            setBoatsVisible(mapState, visible);
            urlSync.update({ boatsOff: visible ? null : true });
          },
        });
        createShipsToggle({ map: mapState.map, shipLayer, urlSync, shown: !initialView.shipsOff });
        createLiberationsToggle({ map: mapState.map, liberationLayer, urlSync, shown: !initialView.liberationsOff });
        initAtlas(mapState.map).then((loaded) => {
          atlas = loaded;
          atlas.setDate(currentDate.toISOString().slice(0, 10));
        });
      }
      currentDate = range.min;
      timeline = initTimeline({
        sliderEl,
        playPauseEl,
    stepBackEl: document.getElementById("step-back"),
    stepForwardEl: document.getElementById("step-forward"),
        dateDisplayEl,
        minDate: range.min,
        maxDate: timelineEnd(range),
        onDateChange: (date) => render(date, true),
      });
      restoreView();
    } else {
      timeline.setRange(range.min, timelineEnd(range));
      render(currentDate, false);
    }

    followWaitingBoat();

    // New boats bring new type labels.
    refreshBoats();
  }

  function followWaitingBoat() {
    if (pendingFollow === null) return;
    const { slug, fromList, restored } = pendingFollow;
    if (routesBySlug.has(slug)) {
      restoring = restored;
      try {
        subjectHooks.follow(slug, { fromList });
      } finally {
        restoring = false;
      }
    } else if (loadIndicator.complete()) {
      pendingFollow = null;
    }
  }

  // Later dates are on their way: the slider already reaches them, and so does a link to one.
  function timelineEnd(range) {
    const ends = [range.max];
    if (lastDeparture !== null) ends.push(lastDeparture);
    if (initialView.date !== undefined && !loadIndicator.complete()) ends.push(parseDate(initialView.date));
    return new Date(Math.max(...ends.map((date) => date.getTime())));
  }

  const loadIndicator = createLoadIndicator(document.getElementById("load-indicator"));

  // Once, after the first routes: the map works without them.
  loadIndicator.firstDrawn
    .then(() => loadLiberations())
    .then((liberations) => {
      places = liberationPlaces(liberations);
      if (currentDate !== null) renderLiberations(currentDate);
    })
    .catch((error) => console.error(error));

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes: loadIndicator.fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => {
      try {
        onData(changed);
      } finally {
        loadIndicator.finish();
      }
    },
    onStatus: (status) => {
      loadIndicator.setTotal(status.patrol_count);
      lastStatus = status;
      if (status.last_departure) lastDeparture = parseDate(status.last_departure);
      const wasEditable = editable;
      editable = canEdit(status);
      battles.setEditable(editable);
      if (editable !== wasEditable && currentDate !== null) {
        render(currentDate, false);
      }
      renderStatusLine();
      loadIndicator.firstDrawn.then(() => loadShips(status.revision));
    },
    onError: (error) => {
      console.error(error);
      liveStatusEl.textContent = NO_CONNECTION;
    },
    setTimer: (fn, ms) => setTimeout(fn, ms),
  });
}

main();

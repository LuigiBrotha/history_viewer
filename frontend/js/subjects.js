import { fetchBoats } from "./api.js";
import { createBoatPanel } from "./boat-panel.js";
import { createSubjectList } from "./subject-list.js";
import { boatSubjects, hitByDate, hitInPeriod, shipSubjects } from "./subject-model.js";
import { inPeriod } from "./status-map.js";

const INERT = { openBoat() {}, openShip() {}, restoreShip() {}, setDate() {}, setPeriod() {}, setRoutes() {}, setShips() {} };

// The U-boten and Schepen in the column Onderwerpen, and what choosing an Onderwerp does: it
// goes into the vak Artikel, and a boat is the Gevolgde boot for as long as the Artikel is about
// it or one of its ships. `hooks` are what each page does on its own map:
//   follow(slug, { fromList }), stopFollow(), followed() the followed slug or null,
//   showShip(hit, { fromList }), showPatrol(patrol, boat).
// fromList is a choice in the column or the search field, not on the map.
export function createSubjects({ battles, urlSync, getShips, hooks = {}, loadBoats = fetchBoats, panel = createBoatPanel }) {
  const column = battles.column;
  if (!column) return INERT;
  const { follow = () => {}, stopFollow = () => {}, followed = () => null, showShip = () => {}, showPatrol = null } = hooks;

  let shipRows = new Map();
  let boatNumbers = new Map();
  let selection = null;
  let routes = [];
  let activeSlugs = null;
  let pendingShip = null;

  const boatList = createSubjectList({
    rootEl: column.sections.boats.bodyEl,
    emptyText: "Geen boten gevonden.",
    onPick: (item) => openBoat(item.key, { fromList: true }),
    onCount: (count) => column.setCount("boats", count),
  });
  const shipList = createSubjectList({
    rootEl: column.sections.ships.bodyEl,
    emptyText: "Geen schepen gevonden.",
    onPick: (item) => openShip(item.hits[0], { fromList: true }),
    onCount: (count) => column.setCount("ships", count),
  });
  column.onSearch((text) => {
    boatList.setSearch(text);
    shipList.setSearch(text);
  });

  const boatPanel = panel({
    article: battles,
    getShips,
    onShowPatrol: showPatrol,
    onOpenBoat: (slug) => openBoat(slug),
    onOpenShip: (hit) => openShip(hit),
  });

  function openBoat(slug, { fromList = false } = {}) {
    boatPanel.open(slug, boatNumbers.get(slug));
    follow(slug, { fromList });
    boatList.reveal(slug);
    shipList.clear();
    urlSync.update({ boat: slug, ship: null });
  }

  function openShip(hit, { fromList = false } = {}) {
    const slug = followed();
    const ship = shipRows.get(hit.ship_external_id);
    const own = slug !== null && (hit.boat_slug === slug || ship?.hits.some((h) => h.boat_slug === slug) === true);
    if (slug !== null && !own) stopFollow();
    const chosen = own ? ship?.hits.find((h) => h.boat_slug === slug) ?? hit : hit;
    boatPanel.openShip(chosen);
    showShip(chosen, { fromList });
    shipList.reveal(chosen.ship_external_id);
    if (!own) boatList.clear();
    urlSync.update({ ship: chosen.ship_external_id, boat: own ? slug : null });
  }

  function release() {
    stopFollow();
    boatList.clear();
    shipList.clear();
    urlSync.update({ boat: null, ship: null });
  }
  battles.onBattleSelected(release);
  battles.onArticleClosed(release);

  function applyMarks() {
    if (selection === null || (selection.date === undefined && selection.from === null && selection.to === null)) {
      boatList.setMarks(null);
      shipList.setMarks(null);
      return;
    }
    if (selection.date !== undefined) {
      boatList.setMarks((item) => activeSlugs?.has(item.key) === true);
      shipList.setMarks((item) => hitByDate(item, selection.date));
      return;
    }
    const { from, to } = selection;
    const active = new Set(routes.filter((patrol) => inPeriod(patrol, from, to)).map((patrol) => patrol.boat_slug));
    boatList.setMarks((item) => active.has(item.key), true);
    shipList.setMarks((item) => hitInPeriod(item, from, to), true);
  }

  function setShips(hits) {
    const items = shipSubjects(hits);
    shipRows = new Map(items.map((item) => [item.key, item]));
    shipList.setItems(items);
    if (pendingShip !== null && shipRows.has(pendingShip)) {
      const key = pendingShip;
      pendingShip = null;
      openShip(shipRows.get(key).hits[0]);
    }
  }

  loadBoats().then(
    (boats) => {
      boatNumbers = new Map(boats.map((boat) => [boat.slug, boat.number]));
      boatList.setItems(boatSubjects(boats));
      applyMarks();
    },
    (error) => console.error(error),
  );

  return {
    openBoat,
    openShip,
    // A ship from the URL: opened as soon as the ships are known.
    restoreShip(key) {
      pendingShip = key;
      if (shipRows.has(key)) setShips(getShips());
    },
    setShips(hits) {
      setShips(hits);
      applyMarks();
    },
    // date is the timeline's ISO date, activeBoats the slugs on patrol then.
    setDate(date, activeBoats) {
      selection = { date };
      activeSlugs = activeBoats;
      applyMarks();
    },
    setPeriod(from, to) {
      selection = { from, to };
      applyMarks();
    },
    setRoutes(next) {
      routes = next;
      applyMarks();
    },
  };
}

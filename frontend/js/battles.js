import { clearBattlePosition, fetchBattlePositions, saveBattlePosition } from "./api.js";
import { activeOn, applyPositions, overlaps } from "./battle-model.js";
import { createBattleLayer } from "./battle-layer.js";
import { createBattlePane } from "./battle-pane.js";
import { initBattleSplit } from "./battle-split.js";
import { createArticlePane } from "./battle-article.js";
import { fetchArticle } from "./api.js";

const BATTLES_URL = "battles/battles.json";

async function loadBattles() {
  const response = await fetch(BATTLES_URL);
  if (!response.ok) {
    throw new Error(`${BATTLES_URL}: ${response.status}`);
  }
  const battles = await response.json();
  if (!Array.isArray(battles)) {
    throw new Error(`${BATTLES_URL}: not a list`);
  }
  return battles;
}

function safeStorage(win) {
  try {
    return win.localStorage;
  } catch {
    return null;
  }
}

// The battles of a page: squares on its map, the resizable pane beside or under it and the
// button that shows it. The file is loaded once. mode "date" is for a page with one selected
// date, which shows the battles active on it; mode "period" is for a page with a period,
// which shows those overlapping it. The page tells the selection through setDate or
// setPeriod and the rest follows. Selecting a battle, in the list, on the map or through a
// link in an article, opens its article beside the list; onBattleChange hears the title, or
// null when the article is closed; onNoposChange hears the "Alleen zonder positie" box being
// ticked or unticked. The page keeps working if the file cannot be loaded.
export function initBattles({
  map,
  mode,
  onPickDate = null,
  onBattleChange = () => {},
  onNoposChange = () => {},
  doc = document,
  win = window,
  load = loadBattles,
  loadArticle = fetchArticle,
  loadPositions = fetchBattlePositions,
  savePosition = saveBattlePosition,
  clearPosition = clearBattlePosition,
}) {
  const splitEl = doc.getElementById("battle-split");
  const paneEl = doc.getElementById("battle-pane");
  if (splitEl === null || paneEl === null) {
    return {
      setDate() {},
      setPeriod() {},
      setEditable() {},
      setOnlyWithoutPosition() {},
      selectBattle: () => false,
      selectedBattle: () => null,
      allBattles: () => [],
      moveEditTo: () => false,
    };
  }
  const storage = safeStorage(win);
  let articleSplit = null;
  const split = initBattleSplit({
    splitEl,
    paneEl,
    dividerEl: doc.getElementById("battle-divider"),
    toggleEl: doc.getElementById("battle-toggle"),
    map,
    storage,
    win,
    reserved: () => (articleSplit?.isOpen() ? articleSplit.size() : 0),
  });
  articleSplit = initBattleSplit({
    splitEl: doc.getElementById("article-split"),
    paneEl: doc.getElementById("article-pane"),
    dividerEl: doc.getElementById("article-divider"),
    toggleEl: null,
    map,
    storage,
    win,
    storageKey: "uboats.articlePane",
    defaultWidth: 520,
    persistOpen: false,
    reserved: () => (split.isOpen() ? split.size() : 0),
  });

  let battles = [];
  let selection = null;
  let editing = null;
  let editHandle = null;
  let editable = false;
  let positionsLoaded = false;
  let selected = null;
  let requested = null;

  const layer = createBattleLayer(map, {
    onBattleClick: (battle) => selectBattle(battle.title),
  });

  const articlePane = createArticlePane({
    rootEl: doc.getElementById("article-pane"),
    load: loadArticle,
    onBattleLink: (title) => selectBattle(title, { pickDate: true }),
    onClose: () => {
      articleSplit.close();
      articlePane.clear();
      selected = null;
      onBattleChange(null);
    },
  });

  const pane = createBattlePane({
    rootEl: paneEl,
    mode,
    onEdit: (battle) => startEdit(battle),
    onClear: (battle) => clearOwn(battle),
    onSelect: (battle) => selectBattle(battle.title, { pickDate: true }),
    onNoposChange,
  });

  // Editing is only offered once the positions are known: saving over positions that
  // could not be read would hide them.
  function applyEditable() {
    const offered = editable && positionsLoaded;
    pane.setEditable(offered);
    if (!offered) cancelEdit();
  }

  // Replaces one battle by a changed copy and shows it, still selected, in the list and on the map.
  function updateBattle(title, change) {
    battles = battles.map((battle) => (battle.title === title ? { ...battle, ...change } : battle));
    const updated = battles.find((battle) => battle.title === title);
    pane.setBattles(battles);
    layer.setBattles(shown());
    layer.setSelected(updated);
    pane.reveal(updated);
  }

  function cancelEdit() {
    if (!editing) return;
    const session = editing;
    editing = null;
    editHandle = null;
    session.stop();
  }

  function startEdit(battle) {
    cancelEdit();
    selectBattle(battle.title);

    const handle = layer.startEdit(battle, {});
    const title = doc.createElement("span");
    title.className = "battle-edit-title";
    title.textContent = battle.title;
    const save = doc.createElement("button");
    save.className = "battle-edit-save";
    save.textContent = "Bewaar";
    save.setAttribute("type", "button");
    const cancel = doc.createElement("button");
    cancel.className = "battle-edit-cancel";
    cancel.textContent = "Annuleer";
    cancel.setAttribute("type", "button");
    const error = doc.createElement("span");
    error.className = "battle-edit-error";
    error.textContent = "Bewaren mislukt.";
    error.hidden = true;
    const barEl = doc.createElement("div");
    barEl.className = "battle-edit-bar";
    barEl.append(title, save, cancel, error);
    const control = L.control({ position: "topleft" });
    control.onAdd = () => {
      L.DomEvent.disableClickPropagation(barEl);
      return barEl;
    };
    control.addTo(map);

    const onKey = (event) => {
      // Esc in the map search field only closes its list.
      if (event.key === "Escape" && !event.target?.closest?.(".map-search")) cancelEdit();
    };
    doc.addEventListener("keydown", onKey);

    const session = {
      battle,
      stop() {
        doc.removeEventListener("keydown", onKey);
        control.remove();
        handle.stop();
      },
    };
    editing = session;
    editHandle = handle;

    save.addEventListener("click", async () => {
      const { lat, lng } = handle.position();
      save.disabled = true;
      cancel.disabled = true;
      error.hidden = true;
      try {
        await savePosition(battle.title, lat, lng);
      } catch (failure) {
        console.error(failure);
        error.hidden = false;
        save.disabled = false;
        cancel.disabled = false;
        return;
      }
      if (editing === session) {
        editing = null;
        editHandle = null;
        session.stop();
      }
      updateBattle(battle.title, { lat, lng, own: true });
    });
    cancel.addEventListener("click", () => cancelEdit());
  }

  async function clearOwn(battle) {
    if (editing?.battle.title === battle.title) cancelEdit();
    try {
      await clearPosition(battle.title);
    } catch (failure) {
      console.error(failure);
      return;
    }
    updateBattle(battle.title, { lat: battle.wikiLat, lng: battle.wikiLng, own: false });
  }

  // pickDate is for the list and the articles: on the timeline page it sets the date to the
  // battle's start. A request made before the file has loaded is applied when it arrives.
  // onResolved(found) hears whether the title is known, once the answer exists.
  function selectBattle(title, { pickDate = false, onResolved = null } = {}) {
    if (!loaded) {
      requested = { title, pickDate, onResolved };
      return true;
    }
    const battle = battles.find((b) => b.title === title);
    if (battle === undefined) {
      onResolved?.(false);
      return false;
    }
    // Selecting another battle ends an edit; a click on the square being edited does not.
    if (editing?.battle.title !== title) cancelEdit();
    if (pickDate && mode === "date") {
      onPickDate?.(battle.start);
    }
    selected = battle.title;
    split.open();
    layer.setSelected(battle);
    layer.showBattle(battle);
    pane.reveal(battle);
    articleSplit.open();
    articlePane.show(battle);
    onBattleChange(battle.title);
    onResolved?.(true);
    return true;
  }

  function shown() {
    if (selection === null) return [];
    return mode === "date" ? activeOn(battles, selection.date) : battles.filter((b) => overlaps(b, selection.from, selection.to));
  }

  function select(next) {
    selection = next;
    pane.setSelection(next);
    layer.setBattles(shown());
  }

  // The Eigen posities are optional: without them the battles stay where the file puts them.
  // Fetched alongside the file rather than after it.
  const positions = loadPositions().then(
    (result) => {
      positionsLoaded = true;
      return result;
    },
    (error) => {
      console.error(error);
      return [];
    },
  );

  let loaded = false;
  load().then(
    async (result) => {
      battles = applyPositions(result, await positions);
      loaded = true;
      pane.setBattles(battles);
      layer.setBattles(shown());
      applyEditable();
      if (requested !== null) {
        const { title, pickDate, onResolved } = requested;
        requested = null;
        selectBattle(title, { pickDate, onResolved });
      }
    },
    (error) => {
      console.error(error);
      pane.showError();
    },
  );

  return {
    setDate: (isoDate) => select({ date: isoDate }),
    setPeriod: (from, to) => select({ from, to }),
    setEditable(next) {
      editable = next;
      applyEditable();
    },
    setOnlyWithoutPosition: (on) => pane.setOnlyWithoutPosition(on),
    selectBattle,
    selectedBattle: () => selected,
    allBattles: () => battles,
    // Moves the square being placed; the position is only stored by Bewaar.
    moveEditTo(lat, lng) {
      if (!editing) return false;
      editHandle.moveTo(lat, lng);
      return true;
    },
  };
}

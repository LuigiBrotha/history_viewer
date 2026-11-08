import { clearBattlePosition, fetchBattlePositions, saveBattlePosition } from "./api.js";
import { activeOn, applyPositions, overlaps } from "./battle-model.js";
import { isTrackLabel, labelKey, matchesLabels, track } from "./battle-labels.js";
import { backupText, readBackup, restorePlan, toCsv, toGeoJson } from "./battle-export.js";
import { createHintLayer } from "./hint-layer.js";
import { createTrackLayer, trackColor } from "./track-layer.js";
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
  download = null,
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
      placeToggle() {},
      step() {},
      editSelected() {},
      save() {},
      saveAndNext() {},
      clearSelected() {},
      toggleArticle() {},
      togglePane() {},
      addLabel() {},
      setLabels() {},
      setLabelMode() {},
      setShowAll() {},
      onLabelModeChange() {},
      onShowAllChange() {},
      labels: () => [],
      onLabelsChange() {},
      setSort() {},
      onSortChange() {},
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
  let lastSelected = null;
  let labels = [];
  let labelMode = "en";
  let showAll = false;
  const labelListeners = [];
  const labelModeListeners = [];
  const showAllListeners = [];
  const sortListeners = [];
  let requested = null;

  const layer = createBattleLayer(map, {
    onBattleClick: (battle) => selectBattle(battle.title),
  });

  const articlePane = createArticlePane({
    rootEl: doc.getElementById("article-pane"),
    load: loadArticle,
    onBattleLink: (title) => selectBattle(title, { pickDate: true }),
    onClose: () => closeArticle(),
  });

  function closeArticle() {
    hintLayer.clear();
    articleSplit.close();
    articlePane.clear();
    selected = null;
    onBattleChange(null);
  }

  const pane = createBattlePane({
    rootEl: paneEl,
    mode,
    onEdit: (battle) => startEdit(battle),
    onClear: (battle) => clearOwn(battle),
    onSelect: (battle) => selectBattle(battle.title, { pickDate: true }),
    onNoposChange,
    onLabelRemove: (label) => changeLabels(labels.filter((l) => labelKey(l) !== labelKey(label))),
    onSortChange: (next) => sortListeners.forEach((listener) => listener(next)),
    onLabelModeChange: (next) => {
      labelMode = next;
      drawSquares();
      labelModeListeners.forEach((listener) => listener(next));
    },
    onShowAllChange: (on) => {
      showAll = on;
      drawSquares();
      showAllListeners.forEach((listener) => listener(on));
    },
    onExport: (format) => exportList(format),
    onBackup: () => backupPositions().catch((error) => win.alert?.(`Back-up mislukt: ${error.message}`)),
    onRestore: (text) => restorePositions(text).catch((error) => win.alert?.(`Terugzetten mislukt: ${error.message}`)),
  });

  const trackLayer = createTrackLayer(map);

  // Plaatshints of the selected battle while it has no position; a click while placing that
  // battle moves its square to the hint.
  const hintLayer = createHintLayer(map, {
    onPick: (hint) => {
      if (editing && editing.battle.title === selected) editHandle?.moveTo(hint.lat, hint.lng);
    },
  });

  function showHints(battle) {
    const unplaced = battle && (battle.lat == null || battle.lng == null);
    if (unplaced && battle.hints?.length) hintLayer.show(battle.hints);
    else hintLayer.clear();
  }

  // Each Eenheid or Bevelhebber label draws its Spoor in a colour of its own.
  function drawTracks() {
    const tracked = labels.filter(isTrackLabel);
    const tracks = tracked.map((label) => ({
      battles: track(battles, label),
      color: trackColor(labels, label),
    }));
    trackLayer.setTracks(tracks);
    pane.setTracks(tracks);
  }

  // A file for the viewer to save; the page's own download unless one is given (tests).
  const save = download ?? ((name, type, text) => {
    const url = win.URL.createObjectURL(new win.Blob([text], { type }));
    const link = doc.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    win.setTimeout(() => win.URL.revokeObjectURL(url), 0);
  });

  function exportList(format) {
    const listed = pane.visibleBattles();
    if (format === "geojson") save("veldslagen.geojson", "application/geo+json", toGeoJson(listed));
    else save("veldslagen.csv", "text/csv", toCsv(listed));
  }

  async function backupPositions() {
    save("eigen-posities.json", "application/json", backupText(await loadPositions()));
  }

  // Restores a back-up after asking: where it differs it wins, what it lacks stays. Resolves
  // to whether anything was restored; rejects on a file that is not a back-up.
  async function restorePositions(text, ask = (question) => win.confirm(question)) {
    const backup = readBackup(text);
    const { set, unchanged } = restorePlan(await loadPositions(), backup);
    if (set.length === 0) return false;
    const question = `${set.length} Eigen positie${set.length === 1 ? "" : "s"} terugzetten? `
      + `(${unchanged} ${unchanged === 1 ? "is" : "zijn"} al gelijk)`;
    if (!ask(question)) return false;
    for (const { title, lat, lng } of set) await savePosition(title, lat, lng);
    const restored = new Map(set.map((p) => [p.title, p]));
    battles = battles.map((b) => (restored.has(b.title) ? { ...b, lat: restored.get(b.title).lat, lng: restored.get(b.title).lng, own: true } : b));
    pane.setBattles(battles);
    drawSquares();
    drawTracks();
    return true;
  }

  function applyLabels() {
    pane.setLabels(labels);
    drawSquares();
    drawTracks();
  }

  // A change made in the app is reported, so the page can keep it in the URL.
  function changeLabels(next) {
    labels = next;
    applyLabels();
    labelListeners.forEach((listener) => listener(labels));
  }

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
    drawSquares();
    drawTracks();
    layer.setSelected(updated);
    showHints(updated);
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
    const saveNext = doc.createElement("button");
    saveNext.className = "battle-edit-save-next";
    saveNext.textContent = "Bewaar en volgende";
    saveNext.setAttribute("type", "button");
    saveNext.title = "Bewaar en ga naar de volgende Veldslag zonder positie (Shift+Enter)";
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
    barEl.append(title, save, saveNext, cancel, error);
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

    // Stores the dragged place; with next, goes on to edit the next battle without a position.
    async function store(next) {
      if (save.disabled) return;
      const { lat, lng } = handle.position();
      const buttons = [save, saveNext, cancel];
      buttons.forEach((button) => (button.disabled = true));
      error.hidden = true;
      try {
        await savePosition(battle.title, lat, lng);
      } catch (failure) {
        console.error(failure);
        error.hidden = false;
        buttons.forEach((button) => (button.disabled = false));
        return;
      }
      if (editing === session) {
        editing = null;
        editHandle = null;
        session.stop();
      }
      updateBattle(battle.title, { lat, lng, own: true });
      if (next) {
        const following = pane.nextUnplaced(battle.title);
        if (following) startEdit(following);
      }
    }
    session.store = store;
    save.addEventListener("click", () => store(false));
    saveNext.addEventListener("click", () => store(true));
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
    showHints(battle);
    pane.reveal(battle);
    articleSplit.open();
    articlePane.show(battle);
    onBattleChange(battle.title);
    onResolved?.(true);
    return true;
  }

  // "Toon alle" widens the squares to every battle, those outside the labels dimmed.
  const widened = () => showAll && labels.length > 0;
  const matching = (b) => matchesLabels(b, labels, labelMode);

  function shown() {
    const labelled = battles.filter(matching);
    // A Spoor is shown whole, whatever the date or period.
    const tracked = labels.some(isTrackLabel);
    if (tracked && !widened()) return labelled;
    if (selection === null) return tracked ? labelled : [];
    const base = widened() ? battles : labelled;
    const inPeriod = mode === "date" ? activeOn(base, selection.date) : base.filter((b) => overlaps(b, selection.from, selection.to));
    if (!tracked) return inPeriod;
    const seen = new Set(inPeriod);
    return [...inPeriod, ...labelled.filter((b) => !seen.has(b))];
  }

  function drawSquares() {
    const list = shown();
    const outside = widened() ? new Set(list.filter((b) => !matching(b)).map((b) => b.title)) : new Set();
    layer.setBattles(list, outside);
  }

  function select(next) {
    selection = next;
    pane.setSelection(next);
    drawSquares();
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
      drawSquares();
      drawTracks();
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
    addLabel(label) {
      if (!labels.some((l) => labelKey(l) === labelKey(label))) changeLabels([...labels, label]);
    },
    // Labels from the URL: applied without being reported back.
    setLabels(next) {
      labels = next;
      applyLabels();
    },
    labels: () => labels,
    onLabelsChange: (listener) => labelListeners.push(listener),
    // EN/OF and "Toon alle" from the URL: applied without being reported back.
    setLabelMode(next) {
      labelMode = next === "of" ? "of" : "en";
      pane.setLabelMode(labelMode);
      drawSquares();
    },
    setShowAll(on) {
      showAll = Boolean(on);
      pane.setShowAll(showAll);
      drawSquares();
    },
    onLabelModeChange: (listener) => labelModeListeners.push(listener),
    onShowAllChange: (listener) => showAllListeners.push(listener),
    setSort: (next) => pane.setSort(next),
    onSortChange: (listener) => sortListeners.push(listener),
    exportList,
    backupPositions,
    restorePositions,
    // The keyboard's actions (see shortcuts.js).
    step(direction) {
      const battle = pane.neighbour(direction);
      if (battle) selectBattle(battle.title, { pickDate: true });
    },
    editSelected() {
      const battle = battles.find((b) => b.title === selected);
      if (battle && editable && positionsLoaded) startEdit(battle);
    },
    save: () => editing?.store(false),
    saveAndNext: () => editing?.store(true),
    // The W key asks first, since a wiped Eigen positie cannot be brought back.
    clearSelected(ask = (question) => win.confirm(question)) {
      const battle = battles.find((b) => b.title === selected);
      if (battle?.own && editable && positionsLoaded && ask(`Eigen positie van ${battle.title} wissen?`)) {
        clearOwn(battle);
      }
    },
    toggleArticle() {
      if (articleSplit.isOpen()) {
        lastSelected = selected;
        closeArticle();
      } else if (lastSelected !== null) {
        selectBattle(lastSelected);
      }
    },
    togglePane() {
      if (split.isOpen()) split.close();
      else split.open();
    },
    // Moves the Veldslagen button into the top-left row of map controls, after the ones
    // already there, so the page decides its place in that row.
    placeToggle() {
      const toggleEl = doc.getElementById("battle-toggle");
      if (toggleEl === null) return;
      const control = L.control({ position: "topleft" });
      control.onAdd = () => {
        L.DomEvent.disableClickPropagation(toggleEl);
        return toggleEl;
      };
      control.addTo(map);
    },
    // Moves the square being placed; the position is only stored by Bewaar.
    moveEditTo(lat, lng) {
      if (!editing) return false;
      editHandle.moveTo(lat, lng);
      return true;
    },
  };
}

import { clearBattlePosition, fetchBattlePositions, saveBattlePosition } from "./api.js";
import { activeOn, applyPositions, overlaps } from "./battle-model.js";
import { createBattleLayer } from "./battle-layer.js";
import { createBattlePane } from "./battle-pane.js";
import { initBattleSplit } from "./battle-split.js";

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
// setPeriod and the rest follows. The page keeps working if the file cannot be loaded.
export function initBattles({
  map,
  mode,
  onPickDate = null,
  doc = document,
  win = window,
  load = loadBattles,
  loadPositions = fetchBattlePositions,
  savePosition = saveBattlePosition,
  clearPosition = clearBattlePosition,
}) {
  const splitEl = doc.getElementById("battle-split");
  const paneEl = doc.getElementById("battle-pane");
  if (splitEl === null || paneEl === null) {
    return { setDate() {}, setPeriod() {}, setEditable() {} };
  }
  const split = initBattleSplit({
    splitEl,
    paneEl,
    dividerEl: doc.getElementById("battle-divider"),
    toggleEl: doc.getElementById("battle-toggle"),
    map,
    storage: safeStorage(win),
    win,
  });

  let battles = [];
  let selection = null;
  let editing = null;
  let editable = false;
  let positionsLoaded = false;

  const layer = createBattleLayer(map, {
    onBattleClick: (battle) => {
      if (editing?.battle.title !== battle.title) cancelEdit();
      split.open();
      layer.setSelected(battle);
      pane.reveal(battle);
    },
  });

  const pane = createBattlePane({
    rootEl: paneEl,
    mode,
    onEdit: (battle) => startEdit(battle),
    onClear: (battle) => clearOwn(battle),
    onSelect: (battle) => {
      cancelEdit();
      if (mode === "date") {
        onPickDate?.(battle.start);
      }
      layer.setSelected(battle);
      layer.showBattle(battle);
      pane.reveal(battle);
    },
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
    session.stop();
  }

  function startEdit(battle) {
    cancelEdit();
    split.open();
    layer.setSelected(battle);
    pane.reveal(battle);
    layer.showBattle(battle);

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
      if (event.key === "Escape") cancelEdit();
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
    (loaded) => {
      positionsLoaded = true;
      return loaded;
    },
    (error) => {
      console.error(error);
      return [];
    },
  );

  load().then(
    async (loaded) => {
      battles = applyPositions(loaded, await positions);
      pane.setBattles(battles);
      layer.setBattles(shown());
      applyEditable();
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
  };
}

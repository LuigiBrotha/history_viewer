import { activeOn, overlaps } from "./battle-model.js";
import { createBattleLayer } from "./battle-layer.js";
import { createBattlePane } from "./battle-pane.js";
import { initBattleSplit } from "./battle-split.js";
import { addPacificButton } from "./pacific-view.js";

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
export function initBattles({ map, mode, onPickDate = null, doc = document, win = window, load = loadBattles }) {
  const splitEl = doc.getElementById("battle-split");
  const paneEl = doc.getElementById("battle-pane");
  if (splitEl === null || paneEl === null) {
    return { setDate() {}, setPeriod() {} };
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

  addPacificButton(map);

  let battles = [];
  let selection = null;

  const layer = createBattleLayer(map, {
    onBattleClick: (battle) => {
      split.open();
      layer.setSelected(battle);
      pane.reveal(battle);
    },
  });

  const pane = createBattlePane({
    rootEl: paneEl,
    mode,
    onSelect: (battle) => {
      if (mode === "date") {
        onPickDate?.(battle.start);
      }
      layer.setSelected(battle);
      layer.showBattle(battle);
    },
  });

  function shown() {
    if (selection === null) return [];
    return mode === "date" ? activeOn(battles, selection.date) : battles.filter((b) => overlaps(b, selection.from, selection.to));
  }

  function select(next) {
    selection = next;
    pane.setSelection(next);
    layer.setBattles(shown());
  }

  load().then(
    (loaded) => {
      battles = loaded;
      pane.setBattles(battles);
      layer.setBattles(shown());
    },
    (error) => {
      console.error(error);
      pane.showError();
    },
  );

  return {
    setDate: (isoDate) => select({ date: isoDate }),
    setPeriod: (from, to) => select({ from, to }),
  };
}

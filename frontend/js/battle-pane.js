import {
  AXIS_BOUNDS,
  activeOn,
  bandPosition,
  barPosition,
  datePosition,
  durationText,
  filterBattles,
  overlaps,
  withoutPosition,
  yearMarks,
} from "./battle-model.js";
import { SORT_NAMES, labelText, matchesLabels, sortBattles } from "./battle-labels.js";

const WIKIPEDIA_PREFIX = "https://en.wikipedia.org/";
const LOAD_FAILED = "Veldslagen konden niet worden geladen.";
const NO_MATCH = "Geen veldslagen gevonden.";
const SOURCE = "Bron: Engelse Wikipedia, CC BY-SA 4.0";

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function percent(value) {
  return `${Math.round(value * 100) / 100}%`;
}

// The list of all battles on one axis. Source text only reaches the page as text content.
// Rows are built once; a new date or period only changes the classes of the rows whose
// state changed. In mode "date" the rows active on the date are highlighted; in mode
// "period" the rows overlapping the period are, and the others are dimmed.
// While "Alleen zonder positie" is ticked, the selected battle stays listed even when it has
// a position, so that saving an Eigen positie or clicking a placed square keeps the filter.
export function createBattlePane({
  rootEl, mode, onSelect, onEdit, onClear, onNoposChange, onLabelRemove, onSortChange, onExport, onBackup, onRestore,
}) {
  let rows = [];
  // The rows in the chosen sort order; rows itself stays in date order.
  let order = [];
  let labels = [];
  let sort = "datum";
  let editable = false;
  let actionsEl = null;
  let selection = null;
  let revealed = null;

  const title = element("h2", "battle-pane-title", "Veldslagen");
  const search = element("input", "battle-search");
  search.setAttribute("type", "search");
  search.setAttribute("placeholder", "Zoek op naam of plaats");
  search.setAttribute("aria-label", "Zoek een veldslag");
  search.setAttribute("autocomplete", "off");
  const head = element("div", "battle-pane-head");
  head.append(title, search);
  const noposBox = element("input", "battle-nopos-filter");
  noposBox.setAttribute("type", "checkbox");
  noposBox.checked = false;
  const noposText = element("span", "battle-nopos-text");
  const noposRow = element("label", "battle-nopos-row");
  noposRow.append(noposBox, noposText);
  const labelsEl = element("div", "battle-labels");
  labelsEl.hidden = true;
  const sortSelect = element("select", "battle-sort");
  sortSelect.setAttribute("aria-label", "Sorteer de veldslagen");
  for (const [value, name] of Object.entries(SORT_NAMES)) {
    const option = element("option", "", `Sorteer: ${name.toLowerCase()}`);
    option.setAttribute("value", value);
    sortSelect.appendChild(option);
  }
  sortSelect.value = sort;
  noposRow.appendChild(sortSelect);

  const axis = element("div", "battle-axis");
  for (const { year, fraction } of yearMarks(AXIS_BOUNDS)) {
    const mark = element("span", "battle-year", String(year));
    mark.style.setProperty("--pos", String(fraction));
    axis.appendChild(mark);
  }

  const marker = element("div", "battle-marker");
  const band = element("div", "battle-band");
  marker.hidden = true;
  band.hidden = true;
  const empty = element("p", "battle-empty", NO_MATCH);
  empty.hidden = true;
  const list = element("ul", "battle-list");
  const track = element("div", "battle-track");
  track.append(mode === "date" ? marker : band, list);
  const scroll = element("div", "battle-scroll");
  scroll.append(empty, track);
  const source = element("p", "battle-source", SOURCE);

  // Export of the listed battles, and a back-up of the Eigen posities (restoring only where
  // editing is offered).
  const tools = element("details", "battle-tools");
  const button = (className, text, handler) => {
    const node = element("button", className, text);
    node.setAttribute("type", "button");
    node.addEventListener("click", handler);
    return node;
  };
  const restoreInput = element("input", "battle-restore-file");
  restoreInput.setAttribute("type", "file");
  restoreInput.setAttribute("accept", "application/json,.json");
  restoreInput.hidden = true;
  restoreInput.addEventListener("change", async () => {
    const file = restoreInput.files?.[0];
    restoreInput.value = "";
    if (file) onRestore?.(await file.text());
  });
  const restoreButton = button("battle-restore", "Eigen posities terugzetten…", () => restoreInput.click());
  restoreButton.hidden = true;
  tools.append(
    element("summary", "battle-tools-summary", "Exporteren en back-up"),
    button("battle-export-csv", "Lijst als CSV", () => onExport?.("csv")),
    button("battle-export-geojson", "Lijst als GeoJSON", () => onExport?.("geojson")),
    button("battle-backup", "Back-up Eigen posities", () => onBackup?.()),
    restoreButton,
    restoreInput,
  );

  rootEl.replaceChildren(head, noposRow, labelsEl, axis, scroll, tools, source);

  function renderLabels() {
    labelsEl.replaceChildren(...labels.map((label) => {
      const chip = element("span", "battle-filter");
      const remove = element("button", "battle-filter-remove", "✕");
      remove.setAttribute("type", "button");
      remove.setAttribute("aria-label", `Verwijder ${labelText(label)}`);
      remove.addEventListener("click", () => onLabelRemove?.(label));
      chip.append(element("span", "battle-filter-text", labelText(label)), remove);
      return chip;
    }));
    labelsEl.hidden = labels.length === 0;
  }

  function applyOrder() {
    const byBattle = new Map(rows.map((r) => [r.battle, r]));
    order = sortBattles(rows.map((r) => r.battle), sort).map((battle) => byBattle.get(battle));
    list.replaceChildren(...order.map((r) => r.el));
  }

  function buildRow(battle, index) {
    const row = element("li", "battle-row");
    row.setAttribute("data-index", String(index));

    const name = element("button", "battle-row-title", battle.title);
    name.setAttribute("type", "button");
    const meta = element("div", "battle-row-meta");
    if (battle.lang && battle.lang !== "en") {
      meta.appendChild(element("span", "battle-lang", battle.lang.toUpperCase()));
    }
    meta.append(element("span", "battle-row-dates", battle.date_text), element("span", "battle-row-duration", durationText(battle)));
    if (battle.own) {
      meta.appendChild(element("span", "battle-ownpos", "eigen positie"));
    } else if (battle.lat == null || battle.lng == null) {
      meta.appendChild(element("span", "battle-nopos", "geen positie"));
    }
    const bar = element("div", "battle-bar");
    const position = barPosition(battle, AXIS_BOUNDS);
    bar.style.setProperty("--left", percent(position.left));
    bar.style.setProperty("--width", percent(position.width));
    const barTrack = element("div", "battle-bar-track");
    barTrack.appendChild(bar);

    row.append(name, meta, barTrack);
    if (typeof battle.url === "string" && battle.url.startsWith(WIKIPEDIA_PREFIX)) {
      const link = element("a", "battle-row-link", "Wikipedia");
      link.setAttribute("href", battle.url);
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
      row.appendChild(link);
    }
    return { battle, el: row, active: false, dimmed: false };
  }

  // The buttons of the selected row, only while editing is offered.
  function refreshActions() {
    actionsEl?.remove();
    actionsEl = null;
    if (!editable || revealed === null) return;
    const { battle } = revealed;
    const actions = element("div", "battle-row-actions");
    const edit = element("button", "battle-row-edit", "Positie aanpassen");
    edit.setAttribute("type", "button");
    edit.addEventListener("click", () => onEdit?.(battle));
    actions.appendChild(edit);
    if (battle.own) {
      const clear = element("button", "battle-row-clear", "Eigen positie wissen");
      clear.setAttribute("type", "button");
      clear.addEventListener("click", () => onClear?.(battle));
      actions.appendChild(clear);
    }
    actionsEl = actions;
    revealed.el.appendChild(actions);
  }

  list.addEventListener("click", (event) => {
    if (event.target.closest("a") || event.target.closest(".battle-row-actions")) return;
    const row = event.target.closest(".battle-row");
    if (row) onSelect?.(rows[Number(row.getAttribute("data-index"))].battle);
  });

  function applyFilter() {
    const battles = rows.map((r) => r.battle).filter((battle) => matchesLabels(battle, labels));
    const unplaced = withoutPosition(battles, mode, selection, search.value);
    noposText.textContent = `Alleen zonder positie (${unplaced.length})`;
    const shown = new Set(noposBox.checked ? unplaced : filterBattles(battles, search.value));
    if (noposBox.checked && revealed !== null) shown.add(revealed.battle);
    for (const row of rows) {
      row.el.hidden = !shown.has(row.battle);
    }
    title.textContent = `Veldslagen (${shown.size})`;
    empty.hidden = shown.size > 0 || rows.length === 0;
  }

  search.addEventListener("input", applyFilter);
  sortSelect.addEventListener("change", () => {
    sort = sortSelect.value;
    applyOrder();
    onSortChange?.(sort);
  });
  noposBox.addEventListener("change", () => {
    applyFilter();
    onNoposChange?.(noposBox.checked);
  });

  function applySelection() {
    if (selection === null) return;
    let isActive;
    let neutral = false;
    if (mode === "date") {
      const activeBattles = new Set(activeOn(rows.map((r) => r.battle), selection.date));
      isActive = (battle) => activeBattles.has(battle);
      marker.hidden = false;
      marker.style.setProperty("--pos", String(datePosition(selection.date, AXIS_BOUNDS)));
    } else {
      neutral = selection.from === null && selection.to === null;
      isActive = (battle) => overlaps(battle, selection.from, selection.to);
      const shaded = bandPosition(selection.from, selection.to, AXIS_BOUNDS);
      band.hidden = neutral;
      band.style.setProperty("--from", String(shaded.from));
      band.style.setProperty("--to", String(shaded.to));
    }
    for (const row of rows) {
      const active = !neutral && isActive(row.battle);
      const dimmed = mode === "period" && !neutral && !active;
      if (active !== row.active) {
        row.active = active;
        row.el.classList.toggle("active", active);
      }
      if (dimmed !== row.dimmed) {
        row.dimmed = dimmed;
        row.el.classList.toggle("dimmed", dimmed);
      }
    }
  }

  return {
    setBattles(battles) {
      const sorted = [...battles].sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : a.title < b.title ? -1 : a.title > b.title ? 1 : 0));
      rows = sorted.map(buildRow);
      applyOrder();
      revealed = null;
      actionsEl = null;
      applyFilter();
      applySelection();
    },
    // { date } in mode "date", { from, to } in mode "period" (null for an open end).
    setSelection(next) {
      selection = next;
      applyFilter();
      applySelection();
    },
    reveal(battle) {
      const row = rows.find((r) => r.battle === battle);
      if (!row) return;
      if (revealed !== null) revealed.el.classList.toggle("selected", false);
      revealed = row;
      applyFilter();
      if (row.el.hidden) {
        search.value = "";
        applyFilter();
      }
      row.el.classList.toggle("selected", true);
      refreshActions();
      row.el.scrollIntoView?.({ block: "center" });
    },
    // The visible battle before (-1) or after (1) the selected one; without one, the last or first.
    neighbour(direction) {
      const visible = order.filter((r) => !r.el.hidden);
      if (!visible.length) return null;
      const index = revealed === null ? -1 : visible.indexOf(revealed);
      if (index === -1) return (direction > 0 ? visible[0] : visible[visible.length - 1]).battle;
      return visible[index + direction]?.battle ?? null;
    },
    // The first visible battle without a position after the one with this title.
    nextUnplaced(title) {
      const visible = order.filter((r) => !r.el.hidden);
      const index = visible.findIndex((r) => r.battle.title === title);
      return visible.slice(index + 1).find((r) => r.battle.lat == null || r.battle.lng == null)?.battle ?? null;
    },
    setEditable(next) {
      editable = next;
      restoreButton.hidden = !editable;
      refreshActions();
    },
    // The listed battles, in the order shown.
    visibleBattles: () => order.filter((r) => !r.el.hidden).map((r) => r.battle),
    // The labels every listed battle must match.
    setLabels(next) {
      labels = next;
      renderLabels();
      applyFilter();
    },
    setSort(next) {
      sort = next in SORT_NAMES ? next : "datum";
      sortSelect.value = sort;
      applyOrder();
    },
    // Ticks or unticks "Alleen zonder positie" without reporting it, as when restoring a URL.
    setOnlyWithoutPosition(on) {
      noposBox.checked = on;
      applyFilter();
    },
    showError() {
      rootEl.replaceChildren(element("p", "battle-error", LOAD_FAILED), source);
    },
  };
}

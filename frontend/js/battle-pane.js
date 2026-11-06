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
export function createBattlePane({ rootEl, mode, onSelect, onEdit, onClear }) {
  let rows = [];
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

  rootEl.replaceChildren(head, noposRow, axis, scroll, source);

  function buildRow(battle, index) {
    const row = element("li", "battle-row");
    row.setAttribute("data-index", String(index));

    const name = element("button", "battle-row-title", battle.title);
    name.setAttribute("type", "button");
    const meta = element("div", "battle-row-meta");
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
    const battles = rows.map((r) => r.battle);
    const unplaced = withoutPosition(battles, mode, selection, search.value);
    noposText.textContent = `Alleen zonder positie (${unplaced.length})`;
    const shown = new Set(noposBox.checked ? unplaced : filterBattles(battles, search.value));
    for (const row of rows) {
      row.el.hidden = !shown.has(row.battle);
    }
    title.textContent = `Veldslagen (${shown.size})`;
    empty.hidden = shown.size > 0 || rows.length === 0;
  }

  search.addEventListener("input", applyFilter);
  noposBox.addEventListener("change", applyFilter);

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
      list.replaceChildren(...rows.map((r) => r.el));
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
      if (row.el.hidden) {
        search.value = "";
        noposBox.checked = false;
        applyFilter();
      }
      if (revealed !== null) revealed.el.classList.toggle("selected", false);
      revealed = row;
      row.el.classList.toggle("selected", true);
      refreshActions();
      row.el.scrollIntoView?.({ block: "center" });
    },
    setEditable(next) {
      editable = next;
      refreshActions();
    },
    showError() {
      rootEl.replaceChildren(element("p", "battle-error", LOAD_FAILED), source);
    },
  };
}

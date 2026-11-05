import {
  AXIS_BOUNDS,
  activeOn,
  bandPosition,
  barPosition,
  datePosition,
  durationText,
  filterBattles,
  overlaps,
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
export function createBattlePane({ rootEl, mode, onSelect }) {
  let rows = [];
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

  rootEl.replaceChildren(head, axis, scroll, source);

  function buildRow(battle, index) {
    const row = element("li", "battle-row");
    row.setAttribute("data-index", String(index));

    const name = element("button", "battle-row-title", battle.title);
    name.setAttribute("type", "button");
    const meta = element("div", "battle-row-meta");
    meta.append(element("span", "battle-row-dates", battle.date_text), element("span", "battle-row-duration", durationText(battle)));
    if (battle.lat == null || battle.lng == null) {
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

  list.addEventListener("click", (event) => {
    if (event.target.closest("a")) return;
    const row = event.target.closest(".battle-row");
    if (row) onSelect?.(rows[Number(row.getAttribute("data-index"))].battle);
  });

  function applyFilter() {
    const shown = new Set(filterBattles(rows.map((r) => r.battle), search.value));
    for (const row of rows) {
      row.el.hidden = !shown.has(row.battle);
    }
    title.textContent = `Veldslagen (${shown.size})`;
    empty.hidden = shown.size > 0 || rows.length === 0;
  }

  search.addEventListener("input", applyFilter);

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
      applyFilter();
      applySelection();
    },
    // { date } in mode "date", { from, to } in mode "period" (null for an open end).
    setSelection(next) {
      selection = next;
      applySelection();
    },
    reveal(battle) {
      const row = rows.find((r) => r.battle === battle);
      if (!row) return;
      if (row.el.hidden) {
        search.value = "";
        applyFilter();
      }
      if (revealed !== null) revealed.el.classList.toggle("selected", false);
      revealed = row;
      row.el.classList.toggle("selected", true);
      row.el.scrollIntoView?.({ block: "center" });
    },
    showError() {
      rootEl.replaceChildren(element("p", "battle-error", LOAD_FAILED), source);
    },
  };
}

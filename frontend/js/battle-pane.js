import {
  AXIS_BOUNDS,
  activeOn,
  bandPosition,
  barPosition,
  datePosition,
  displayTitle,
  durationText,
  filterBattles,
  overlaps,
  titleNote,
  isRefining,
  withoutPosition,
  yearMarks,
} from "./battle-model.js";
import { SORT_NAMES, labelText, matchesLabels, sortBattles } from "./battle-labels.js";
import { placeText } from "./hint-layer.js";
import { FULL_RANGE, STEPS, inSpreadRange, rangeForSteps, rangeText, stepForKm } from "./spread.js";
import { trackColor } from "./track-layer.js";

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
  rootEl, mode, searchEl = null, titleEl = null, onSearchCleared, onSelect, onEdit, onClear, onNoposChange, onLabelRemove, onLabelsClear, onSortChange, onExport, onBackup, onRestore,
  onLabelModeChange, onShowAllChange, onSpreadChange,
}) {
  let rows = [];
  // The step numbers of the Sporen per battle title: [{ number, color }].
  let steps = new Map();
  // Per battle title, the middle and spread of its Plaatshints (see placeText).
  let placeSummary = {};
  // The rows in the chosen sort order; rows itself stays in date order.
  let order = [];
  let labels = [];
  // "en": a battle must match every label, "of": one is enough.
  let labelMode = "en";
  // Every battle listed, those outside the labels dimmed.
  let showAll = false;
  let sort = "datum";
  // title → place among the battles found in the texts, best first; null without such a search.
  let textHits = null;
  let editable = false;
  let actionsEl = null;
  let selection = null;
  let revealed = null;

  // In the column Onderwerpen the search field and the title are the column's.
  const title = titleEl ?? element("h2", "battle-pane-title", "Veldslagen");
  const search = searchEl ?? element("input", "battle-search");
  if (!searchEl) {
    search.setAttribute("type", "search");
    search.setAttribute("placeholder", "Zoek op naam of plaats");
    search.setAttribute("aria-label", "Zoek een veldslag");
    search.setAttribute("autocomplete", "off");
  }
  const head = element("div", "battle-pane-head");
  if (!searchEl) head.append(title, search);
  const noposBox = element("input", "battle-nopos-filter");
  noposBox.setAttribute("type", "checkbox");
  noposBox.checked = false;
  const noposText = element("span", "battle-nopos-text");
  const noposRow = element("label", "battle-nopos-row");
  noposRow.append(noposBox, noposText);
  const labelsEl = element("div", "battle-labels");
  labelsEl.hidden = true;
  const clearButton = element("button", "battle-filter-clear", "Wis alles");
  clearButton.setAttribute("type", "button");
  clearButton.addEventListener("click", () => onLabelsClear?.());
  const modeButton = element("button", "battle-filter-mode", "EN");
  modeButton.setAttribute("type", "button");
  modeButton.setAttribute("title", "EN: aan alle filters voldoen, OF: aan één filter voldoen");
  const allBox = element("input", "battle-filter-all");
  allBox.setAttribute("type", "checkbox");
  allBox.checked = false;
  const allRow = element("label", "battle-filter-all-row");
  allRow.append(allBox, element("span", "battle-filter-all-text", "Toon alle"));
  const sortSelect = element("select", "battle-sort");
  sortSelect.setAttribute("aria-label", "Sorteer de veldslagen");
  for (const [value, name] of Object.entries(SORT_NAMES)) {
    const option = element("option", "", `Sorteer: ${name.toLowerCase()}`);
    option.setAttribute("value", value);
    sortSelect.appendChild(option);
  }
  sortSelect.value = sort;
  noposRow.appendChild(sortSelect);

  // The Spreiding range: two handles on one track, on a log scale (see spread.js).
  let spreadRange = FULL_RANGE;
  const spreadRow = element("div", "battle-spread-row");
  const spreadText = element("span", "battle-spread-text", rangeText(spreadRange));
  const spreadTrack = element("div", "battle-spread-track");
  const spreadInput = (label, value) => {
    const input = element("input", "battle-spread-input");
    input.setAttribute("type", "range");
    input.setAttribute("min", "0");
    input.setAttribute("max", String(STEPS));
    input.setAttribute("step", "1");
    input.setAttribute("aria-label", label);
    input.value = String(value);
    return input;
  };
  const spreadLow = spreadInput("Kleinste spreiding", 0);
  const spreadHigh = spreadInput("Grootste spreiding", STEPS);
  spreadTrack.append(spreadLow, spreadHigh);
  spreadRow.append(spreadText, spreadTrack);

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

  rootEl.replaceChildren(...(searchEl ? [] : [head]), noposRow, spreadRow, labelsEl, axis, scroll, tools, source);

  function renderLabels() {
    labelsEl.replaceChildren(...labels.map((label) => {
      const chip = element("span", "battle-filter");
      const remove = element("button", "battle-filter-remove", "✕");
      remove.setAttribute("type", "button");
      remove.setAttribute("aria-label", `Verwijder ${labelText(label)}`);
      remove.addEventListener("click", () => onLabelRemove?.(label));
      const color = trackColor(labels, label);
      if (color) {
        const swatch = element("span", "battle-filter-swatch");
        swatch.style.background = color;
        chip.append(swatch);
      }
      chip.append(element("span", "battle-filter-text", labelText(label)), remove);
      return chip;
    }), modeButton, clearButton, allRow);
    labelsEl.hidden = labels.length === 0;
  }

  function applyOrder() {
    const byBattle = new Map(rows.map((r) => [r.battle, r]));
    const sorted = sortBattles(rows.map((r) => r.battle), sort);
    if (textHits !== null) {
      const placeOf = (battle) => textHits.get(battle.title) ?? textHits.size;
      sorted.sort((a, b) => placeOf(a) - placeOf(b));
    }
    order = sorted.map((battle) => byBattle.get(battle));
    list.replaceChildren(...order.map((r) => r.el));
  }

  function buildRow(battle, index) {
    const row = element("li", "battle-row");
    row.setAttribute("data-index", String(index));

    const name = element("button", "battle-row-title", displayTitle(battle));
    const note = titleNote(battle);
    if (note) name.setAttribute("title", note);
    name.setAttribute("type", "button");
    const meta = element("div", "battle-row-meta");
    const stepsEl = element("span", "battle-row-steps");
    meta.appendChild(stepsEl);
    if (battle.lang && battle.lang !== "en") {
      meta.appendChild(element("span", "battle-lang", battle.lang.toUpperCase()));
    }
    meta.append(element("span", "battle-row-dates", battle.date_text), element("span", "battle-row-duration", durationText(battle)));
    const placesEl = element("span", "battle-row-places");
    if (battle.own) {
      meta.appendChild(element("span", "battle-ownpos", "eigen positie"));
    } else if (isRefining(battle)) {
      meta.appendChild(element("span", "battle-nopos battle-refine", "nog te verfijnen"));
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
    meta.appendChild(placesEl);
    const entry = { battle, el: row, stepsEl, placesEl, active: false, dimmed: false };
    renderSteps(entry);
    renderPlaces(entry);
    return entry;
  }

  function renderPlaces({ battle, placesEl }) {
    const text = placeText(battle, placeSummary[battle.title]);
    placesEl.textContent = text;
    placesEl.hidden = !text;
  }

  function renderSteps({ battle, stepsEl }) {
    stepsEl.replaceChildren(...(steps.get(battle.title) ?? []).map(({ number, color }) => {
      const step = element("span", "battle-row-step", String(number));
      step.style.background = color;
      return step;
    }));
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
    const all = rows.map((r) => r.battle);
    const matching = new Set(all.filter((battle) => matchesLabels(battle, labels, labelMode)));
    const widened = showAll && labels.length > 0;
    const inSpread = (battle) => inSpreadRange(placeSummary[battle.title], spreadRange);
    const battles = (widened ? all : all.filter((battle) => matching.has(battle))).filter(inSpread);
    const found = (list) => {
      const byName = new Set(filterBattles(list, search.value));
      return list.filter((battle) => byName.has(battle) || textHits?.has(battle.title) === true);
    };
    const unplaced = found(withoutPosition(battles, mode, selection, ""));
    noposText.textContent = `Alleen zonder positie (${unplaced.length})`;
    const shown = new Set(noposBox.checked ? unplaced : found(battles));
    if (noposBox.checked && revealed !== null) shown.add(revealed.battle);
    for (const row of rows) {
      row.el.hidden = !shown.has(row.battle);
      row.el.classList.toggle("outside-filter", widened && !matching.has(row.battle));
    }
    const inside = [...shown].filter((battle) => matching.has(battle)).length;
    title.textContent = widened ? `Veldslagen (${inside} van ${shown.size})` : `Veldslagen (${shown.size})`;
    empty.hidden = shown.size > 0 || rows.length === 0;
  }

  search.addEventListener("input", applyFilter);

  function showSpread() {
    spreadLow.value = String(stepForKm(spreadRange.min));
    spreadHigh.value = String(spreadRange.max === null ? STEPS : stepForKm(spreadRange.max));
    spreadText.textContent = rangeText(spreadRange);
  }
  // A handle may not pass the other: the one being moved stops there.
  const onSpreadInput = (moved) => () => {
    let low = Number(spreadLow.value);
    let high = Number(spreadHigh.value);
    if (low > high) {
      if (moved === spreadLow) low = high;
      else high = low;
    }
    spreadRange = rangeForSteps(low, high);
    showSpread();
    applyFilter();
    onSpreadChange?.(spreadRange);
  };
  spreadLow.addEventListener("input", onSpreadInput(spreadLow));
  spreadHigh.addEventListener("input", onSpreadInput(spreadHigh));
  function showLabelMode() {
    modeButton.textContent = labelMode.toUpperCase();
    modeButton.setAttribute("aria-label", labelMode === "of" ? "Filters: één is genoeg" : "Filters: alle moeten kloppen");
  }
  modeButton.addEventListener("click", () => {
    labelMode = labelMode === "en" ? "of" : "en";
    showLabelMode();
    applyFilter();
    onLabelModeChange?.(labelMode);
  });
  allBox.addEventListener("change", () => {
    showAll = allBox.checked;
    applyFilter();
    onShowAllChange?.(showAll);
  });
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
        onSearchCleared?.();
      }
      row.el.classList.toggle("selected", true);
      refreshActions();
      row.el.scrollIntoView?.({ block: "center" });
    },
    // No battle is chosen any more: the vak Artikel shows something else.
    unreveal() {
      if (revealed === null) return;
      revealed.el.classList.toggle("selected", false);
      revealed = null;
      refreshActions();
      applyFilter();
    },
    // The titles found in the texts, best first: those battles are listed too, at the top. Null ends it.
    setTextHits(titles) {
      textHits = titles === null ? null : new Map(titles.map((title, place) => [title, place]));
      applyOrder();
      applyFilter();
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
    setPlaceSummary(summary) {
      placeSummary = summary ?? {};
      rows.forEach(renderPlaces);
      applyFilter();
    },
    // From the URL or the page: not reported back.
    setSpreadRange(range) {
      spreadRange = range;
      showSpread();
      applyFilter();
    },
    // The Sporen drawn on the map: [{ battles (in order), color }]; each battle shows its number.
    setTracks(tracks) {
      steps = new Map();
      for (const { battles, color } of tracks) {
        battles.forEach((battle, index) => {
          if (!steps.has(battle.title)) steps.set(battle.title, []);
          steps.get(battle.title).push({ number: index + 1, color });
        });
      }
      rows.forEach(renderSteps);
    },
    // From the URL or the page: not reported back.
    setLabelMode(next) {
      labelMode = next === "of" ? "of" : "en";
      showLabelMode();
      applyFilter();
    },
    setShowAll(on) {
      showAll = Boolean(on);
      allBox.checked = showAll;
      applyFilter();
    },
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

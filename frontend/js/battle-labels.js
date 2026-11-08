import { displayTitle, durationDays } from "./battle-model.js";

// Labels: filters on the Veldslagen chosen through the search field, such as "Land: Polen".
// A battle must match every label. Pure: the pane and the pages decide what to show.

const KAMP_NAMES = { as: "As", westers: "Westerse geallieerden", sovjet: "Sovjet-Unie", overig: "Overig" };
const WINNER_NAMES = { ...KAMP_NAMES, onbeslist: "onbeslist", onbekend: "onbekend" };
const LANGUAGE_NAMES = { en: "Engels", nl: "Nederlands", de: "Duits", pl: "Pools" };
const POSITION_NAMES = { eigen: "eigen positie", wikipedia: "Wikipedia-positie" };
const KIND_NAMES = {
  land: "Land", bevelhebber: "Bevelhebber", eenheid: "Eenheid", winnaar: "Winnaar", taal: "Taal", positie: "Positie",
};
// Labels whose value is a name from the battles themselves, each read from its own list.
const NAMED = { land: "countries", bevelhebber: "commanders", eenheid: "units" };
// An Eenheid or Bevelhebber label also draws a Spoor.
const TRACKS = new Set(["bevelhebber", "eenheid"]);
const FIXED = { winnaar: WINNER_NAMES, taal: LANGUAGE_NAMES, positie: POSITION_NAMES };
const MAX_NAMES = 8;

function matches(battle, { kind, value }) {
  const winner = Array.isArray(battle.winner) ? battle.winner : [];
  switch (kind) {
    case "land":
    case "bevelhebber":
    case "eenheid":
      return Array.isArray(battle[NAMED[kind]]) && battle[NAMED[kind]].includes(value);
    case "winnaar":
      if (value === "onbeslist") return winner.length === 2;
      if (value === "onbekend") return winner.length === 0;
      return winner.length === 1 && winner[0] === value;
    case "taal":
      return (battle.lang ?? "en") === value;
    case "positie":
      if (value === "eigen") return Boolean(battle.own);
      return !battle.own && battle.lat != null && battle.lng != null;
    default:
      return true;
  }
}

// "en": every label must match; "of": one is enough. Without labels every battle matches.
export function matchesLabels(battle, labels, mode = "en") {
  if (labels.length === 0) return true;
  const test = (label) => matches(battle, label);
  return mode === "of" ? labels.some(test) : labels.every(test);
}

export function labelText({ kind, value }) {
  const name = kind in NAMED ? value : FIXED[kind]?.[value] ?? value;
  return `${KIND_NAMES[kind]}: ${name}`;
}

export function labelKey({ kind, value }) {
  return `${kind}:${value}`;
}

function valid({ kind, value }) {
  if (kind in NAMED) return value.length > 0;
  return kind in FIXED && value in FIXED[kind];
}

// "land:Polen,winnaar:as" in the URL; each value is encoded, so commas inside stay.
export function writeLabels(labels) {
  return labels.map(({ kind, value }) => `${kind}:${encodeURIComponent(value)}`).join(",");
}

export function readLabels(text) {
  if (!text) return [];
  const labels = [];
  for (const part of String(text).split(",")) {
    const colon = part.indexOf(":");
    if (colon < 0) continue;
    let value;
    try {
      value = decodeURIComponent(part.slice(colon + 1));
    } catch {
      continue;
    }
    const label = { kind: part.slice(0, colon), value };
    if (valid(label) && !labels.some((l) => labelKey(l) === labelKey(label))) labels.push(label);
  }
  return labels;
}

function suggestion(label) {
  return { label: labelText(label), sub: "", item: label };
}

// The labels a query could mean: names that occur in the battles (Landen, Bevelhebbers,
// Eenheden), then the fixed ones.
export function searchLabels(battles, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  const results = [];
  for (const [kind, field] of Object.entries(NAMED)) {
    const names = new Set();
    for (const battle of battles) {
      for (const name of battle[field] ?? []) {
        if (name.toLowerCase().includes(needle)) names.add(name);
      }
    }
    results.push(...[...names].sort((a, b) => a.localeCompare(b, "nl")).slice(0, MAX_NAMES)
      .map((value) => suggestion({ kind, value })));
  }
  for (const [kind, names] of Object.entries(FIXED)) {
    for (const [value, name] of Object.entries(names)) {
      if (name.toLowerCase().includes(needle) || KIND_NAMES[kind].toLowerCase().startsWith(needle)) {
        results.push(suggestion({ kind, value }));
      }
    }
  }
  return results;
}

const SORTS = {
  datum: (a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : displayTitle(a).localeCompare(displayTitle(b), "nl")),
  naam: (a, b) => displayTitle(a).localeCompare(displayTitle(b), "nl", { sensitivity: "base" }),
  duur: (a, b) => durationDays(b) - durationDays(a) || SORTS.datum(a, b),
};
export const SORT_NAMES = { datum: "Datum", naam: "Naam", duur: "Duur" };

export function sortBattles(battles, sort = "datum") {
  return [...battles].sort(SORTS[sort] ?? SORTS.datum);
}

export function isTrackLabel(label) {
  return TRACKS.has(label.kind);
}

// The Spoor of an Eenheid or Bevelhebber: its battles with a position, by start date. A battle
// that holds a shorter one of the same Spoor (a campaign around its battles) is left out, so
// that the Spoor follows the smallest battles.
export function track(battles, label) {
  const placed = battles.filter((b) => b.lat != null && b.lng != null && matchesLabels(b, [label]));
  const kept = placed.filter((outer) =>
    !placed.some((inner) => inner !== outer && inner.start >= outer.start && inner.end <= outer.end
      && durationDays(inner) < durationDays(outer)));
  return sortBattles(kept, "datum");
}

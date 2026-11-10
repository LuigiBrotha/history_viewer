import { afwijking, displayTitle, durationDays, isRefining } from "./battle-model.js";
import { trackName } from "./track-layer.js";

// Labels: filters on the Veldslagen chosen through the search field, such as "Land: Polen".
// A battle must match every label. Pure: the pane and the pages decide what to show.

const KAMP_NAMES = { as: "As", westers: "Westerse geallieerden", sovjet: "Sovjet-Unie", overig: "Overig" };
const WINNER_NAMES = { ...KAMP_NAMES, onbeslist: "onbeslist", onbekend: "onbekend" };
export const LANGUAGE_NAMES = {
  en: "Engels", nl: "Nederlands", de: "Duits", pl: "Pools", ru: "Russisch", fr: "Frans", it: "Italiaans", ja: "Japans",
  be: "Belarussisch", ca: "Catalaans", cs: "Tsjechisch", el: "Grieks", es: "Spaans", et: "Ests", fi: "Fins",
  he: "Hebreeuws", hu: "Hongaars", lij: "Ligurisch", lt: "Litouws", lv: "Lets", mk: "Macedonisch", no: "Noors",
  ro: "Roemeens", sh: "Servokroatisch", simple: "Eenvoudig Engels", sk: "Slowaaks", sl: "Sloveens", sr: "Servisch",
  uk: "Oekraïens", zh: "Chinees",
};
const POSITION_NAMES = { eigen: "eigen positie", wikipedia: "Wikipedia-positie", verfijnen: "nog te verfijnen" };
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
      if (value === "verfijnen") return isRefining(battle);
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

// What the infoboxes list as a commander without being a person: leftovers of status templates
// and staffs or forces.
const NOT_A_PERSON = /^(killed in action|wounded in action|pow|prisoner of war|ob west)$|headquarters|task force|forces of the|expeditionary/i;

// A Label per person in the infobox of a Veldslag, each once.
export function commanderLabels(battle) {
  const names = (battle.commanders ?? []).filter((name) => !NOT_A_PERSON.test(trackName(name)));
  return [...new Set(names)].map((value) => ({ kind: "bevelhebber", value }));
}

// A Label per Eenheid in the infobox of a Veldslag, each once.
export function unitLabels(battle) {
  return [...new Set(battle.units ?? [])].map((value) => ({ kind: "eenheid", value }));
}

export function labelText({ kind, value }) {
  const fallback = kind === "taal" ? value.toUpperCase() : value;
  const name = kind in NAMED ? value : FIXED[kind]?.[value] ?? fallback;
  return `${KIND_NAMES[kind]}: ${name}`;
}

export function labelKey({ kind, value }) {
  return `${kind}:${value}`;
}

function valid({ kind, value }) {
  if (kind in NAMED) return value.length > 0;
  // Any Wikipedia's code, not only those with a Dutch name.
  if (kind === "taal") return /^[a-z]{2,3}(?:-[a-z]+)?$/.test(value);
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
  const languages = { ...LANGUAGE_NAMES };
  for (const battle of battles) {
    if (battle.lang && !(battle.lang in languages)) languages[battle.lang] = battle.lang.toUpperCase();
  }
  for (const [kind, names] of Object.entries({ ...FIXED, taal: languages })) {
    for (const [value, name] of Object.entries(names)) {
      if (name.toLowerCase().includes(needle) || KIND_NAMES[kind].toLowerCase().startsWith(needle)) {
        results.push(suggestion({ kind, value }));
      }
    }
  }
  return results;
}

// By Afwijking, largest (direction -1) or smallest (1) first; battles without one last, by date.
function byAfwijking(direction, summaries) {
  return (a, b) => {
    const x = afwijking(a, summaries[a.title]);
    const y = afwijking(b, summaries[b.title]);
    if (x === null || y === null) return Number(x === null) - Number(y === null) || SORTS.datum(a, b);
    return direction * (x - y) || SORTS.datum(a, b);
  };
}

const SORTS = {
  datum: (a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : displayTitle(a).localeCompare(displayTitle(b), "nl")),
  naam: (a, b) => displayTitle(a).localeCompare(displayTitle(b), "nl", { sensitivity: "base" }),
  duur: (a, b) => durationDays(b) - durationDays(a) || SORTS.datum(a, b),
  verfijnen: (a, b) => Number(isRefining(b)) - Number(isRefining(a)) || SORTS.datum(a, b),
};
export const SORT_NAMES = {
  datum: "Datum", naam: "Naam", duur: "Duur", verfijnen: "Nog te verfijnen",
  afwijking: "Grootste afwijking", "afwijking-klein": "Kleinste afwijking",
};

// The summaries of the Plaatshints per title are only needed for the Afwijking.
export function sortBattles(battles, sort = "datum", summaries = {}) {
  const order = sort === "afwijking" ? byAfwijking(-1, summaries)
    : sort === "afwijking-klein" ? byAfwijking(1, summaries)
      : SORTS[sort] ?? SORTS.datum;
  return [...battles].sort(order);
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

// Bevrijdingen: when a place was liberated (or, in an Axis country, taken), and whether it is
// occupied or liberated on a date. Pure: the records come from battles/bevrijdingen.json.
import { periodLabel } from "./tonnage-model.js";

const DARK = "#222";
// Only the Soviet list gives each town its own occupation date; the other occupied countries
// were occupied as a whole from the day the war reached them. The Axis countries and those
// occupied by Japan have no start: they only appear once taken.
const OCCUPATION_STARTS = {
  Nederland: "1940-05-10",
  Polen: "1939-09-01",
  Noorwegen: "1940-04-09",
  Tsjechoslowakije: "1939-03-15",
  Joegoslavië: "1941-04-06",
};

function placeKey(liberation) {
  return `${liberation.source}|${liberation.title ?? liberation.place}`;
}

const byLiberated = (a, b) => (a.liberated < b.liberated ? -1 : a.liberated > b.liberated ? 1 : 0);

// The records of one place in occupations: a record with its own occupation date starts a new
// one (Kharkov fell again in March 1943); one without belongs to the occupation before it, so a
// place listed twice stays liberated from its first date. Only a place's first occupation can
// fall back on its country's start.
export function liberationPlaces(liberations) {
  const groups = new Map();
  for (const liberation of liberations) {
    const key = placeKey(liberation);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(liberation);
  }
  return [...groups].map(([key, records]) => {
    const occupations = [];
    for (const record of [...records].sort(byLiberated)) {
      if (occupations.length === 0 || record.occupied) {
        const start = record.occupied ?? OCCUPATION_STARTS[record.country] ?? record.liberated;
        occupations.push({ start, records: [record] });
      } else {
        occupations.at(-1).records.push(record);
      }
    }
    return { key, occupations };
  });
}

// day is an ISO date. Per place the last occupation begun by then: occupied until its first
// liberation, after that liberated as its newest record says. Nothing before the first one.
export function liberationsOnDate(places, day) {
  const shown = [];
  for (const { key, occupations } of places) {
    const occupation = occupations.findLast((candidate) => candidate.start <= day);
    if (occupation === undefined) continue;
    const [first] = occupation.records;
    if (day < first.liberated) {
      shown.push({ key, liberation: first, state: "occupied" });
    } else {
      shown.push({ key, liberation: occupation.records.findLast((record) => record.liberated <= day), state: "liberated" });
    }
  }
  return shown;
}

// from and to are ISO dates or null (open ended), as for the ships.
export function liberationsInPeriod(liberations, from, to) {
  return liberations
    .filter((liberation) => (from === null || liberation.liberated >= from) && (to === null || liberation.liberated <= to))
    .map((liberation) => ({
      // Two places can share an article (Cadier and Keer), so the place's own name is in the key.
      key: `${placeKey(liberation)}|${liberation.liberated}|${liberation.place}`,
      liberation,
      state: "liberated",
    }));
}

// The Dutch list is of the Western Allies' advance, the Russian lists of the Red Army's.
export function liberationKamp(liberation) {
  return liberation.source === "nl" ? "westers" : "sovjet";
}

// The fill is left to the style sheet: the class win1-<kamp> gives it the same custom property
// as the Veldslag squares, so both keep the same colours.
export function liberationStyle(state, liberation) {
  if (state === "occupied") {
    return { color: DARK, weight: 1.5, fill: false, className: "liberation" };
  }
  return {
    color: DARK,
    weight: 1,
    fill: true,
    fillOpacity: 1,
    className: `liberation liberation-free win1-${liberationKamp(liberation)}`,
  };
}

const dutchDate = (iso) => periodLabel(iso, "day");

export function liberationTooltip(liberation) {
  const parts = [liberation.place && liberation.place !== liberation.name ? `${liberation.name} (${liberation.place})` : liberation.name];
  const occupied = liberation.partial ? "deels bezet" : "bezet";
  if (liberation.occupied) {
    parts.push(`${occupied} sinds ${dutchDate(liberation.occupied)}`);
  } else if (liberation.partial) {
    parts.push(occupied);
  }
  let when = `${liberation.verb ?? "bevrijd"} op ${dutchDate(liberation.liberated)}`;
  if (liberation.date_text) when += ` (${liberation.date_text})`;
  if (liberation.by) when += ` door ${liberation.by}`;
  parts.push(when);
  return parts.join(" — ");
}

const ARTICLES = { ru: "https://ru.wikipedia.org/wiki/", en: "https://en.wikipedia.org/wiki/" };
const indexes = new WeakMap();

// The battles file is the same list until it is reloaded, so its index is made once:
// language → article title → Veldslag title.
function articleTitles(battles) {
  if (!indexes.has(battles)) {
    const index = { ru: new Map(), en: new Map() };
    for (const battle of battles) {
      for (const [lang, prefix] of Object.entries(ARTICLES)) {
        if (!battle.url?.startsWith(prefix)) continue;
        try {
          index[lang].set(decodeURIComponent(battle.url.slice(prefix.length)).replaceAll("_", " "), battle.title);
        } catch {
          // A malformed URL leads nowhere.
        }
      }
    }
    indexes.set(battles, index);
  }
  return indexes.get(battles);
}

// The title of the Veldslag whose article is the operation's: its Russian article, or else the
// English one it links to (most Veldslagen come from the English Wikipedia). Null without one.
export function liberationBattle(liberation, battles) {
  const index = articleTitles(battles);
  return (
    (liberation.operation && index.ru.get(liberation.operation)) ||
    (liberation.operation_en && index.en.get(liberation.operation_en)) ||
    null
  );
}

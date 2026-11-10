// The histogram of /histogram: how often Veldslagen of each length occur, each bar split by
// Benaming (the word the English title uses for the kind of battle). Pure: no DOM.
import { durationDays } from "./battle-model.js";

// In the fixed order of the stack, bottom first; each takes the next colour of the palette,
// the last two the rest.
export const BENAMINGEN = [
  { key: "battle", name: "Battle" },
  { key: "operation", name: "Operation" },
  { key: "offensive", name: "Offensive" },
  { key: "siege", name: "Siege" },
  { key: "campaign", name: "Campaign" },
  { key: "raid", name: "Raid of bombing" },
  { key: "ander", name: "Ander woord" },
  { key: "vertaald", name: "Vertaalde titel" },
];

const WORDS = [
  ["battle", "battles?"],
  ["operation", "operations?"],
  ["offensive", "offensives?"],
  ["siege", "sieges?"],
  ["campaign", "campaigns?"],
  ["raid", "raids?|bombings?"],
];

// The English name: its own title for an English Wikipedia article, else the title of the English
// article on the same battle or its English label on Wikidata; a machine translation is none.
function englishName(battle) {
  if (!battle.lang || battle.lang === "en") return battle.title;
  return battle.title_source === "vertaald" ? null : battle.title_en ?? null;
}

// The Benaming of a battle: the first of the WORDS in its English name, "ander" for an English
// name without one, "vertaald" when it has only a machine-translated title.
export function benamingOf(battle) {
  const title = englishName(battle);
  if (!title) return "vertaald";
  let found = "ander";
  let at = Infinity;
  for (const [key, pattern] of WORDS) {
    const match = new RegExp(`(?<![\\p{L}\\p{N}])(?:${pattern})(?![\\p{L}\\p{N}])`, "iu").exec(title);
    if (match && match.index < at) {
      found = key;
      at = match.index;
    }
  }
  return found;
}

// Each bar holds the lengths up to and including its `max` days.
export const BINS = [
  { name: "1 dag", max: 1 },
  { name: "2–3 dagen", max: 3 },
  { name: "4–7 dagen", max: 7 },
  { name: "1–4 weken", max: 30 },
  { name: "1–3 maanden", max: 91 },
  { name: "3–12 maanden", max: 365 },
  { name: "1–2 jaar", max: 730 },
  { name: "> 2 jaar", max: Infinity },
];

export function binIndex(days) {
  return BINS.findIndex((bin) => days <= bin.max);
}

// Known only by its month or year: its length is a guess.
export function isRough(battle) {
  return battle.precision === "month" || battle.precision === "year";
}

// Per bar: its total and one segment per Benaming (in BENAMINGEN order), each with its battles
// (the rough ones last, by length) and how many of them are rough.
export function histogram(battles) {
  const bars = BINS.map((bin) => ({
    name: bin.name,
    total: 0,
    segments: BENAMINGEN.map(({ key }) => ({ benaming: key, battles: [], rough: 0 })),
  }));
  const keyIndex = new Map(BENAMINGEN.map(({ key }, index) => [key, index]));
  for (const battle of battles) {
    const bar = bars[binIndex(durationDays(battle))];
    const segment = bar.segments[keyIndex.get(benamingOf(battle))];
    segment.battles.push(battle);
    if (isRough(battle)) segment.rough += 1;
    bar.total += 1;
  }
  for (const bar of bars) {
    for (const segment of bar.segments) {
      segment.battles.sort((a, b) => Number(isRough(a)) - Number(isRough(b))
        || durationDays(a) - durationDays(b) || a.title.localeCompare(b.title));
    }
  }
  return bars;
}

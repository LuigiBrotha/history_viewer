const DAY_MS = 24 * 60 * 60 * 1000;
const DAYS_PER_MONTH = 30.44;
const DAYS_PER_YEAR = 365.25;
// Up to here a duration is told in days, from here on in months, and from two years in years.
const MAX_DAYS_IN_DAYS = 60;
const MIN_DAYS_IN_YEARS = 700;
// A one-day battle on a seven-year axis would be thinner than a pixel.
const MIN_BAR_WIDTH = 0.5;
const MAX_NAMED_SQUARES = 25;
const NAMED_FROM_ZOOM = 6;

function dayNumber(iso) {
  return Math.round(Date.parse(iso) / DAY_MS);
}

// Both ends count: a battle on one date lasted one day.
export function durationDays(battle) {
  return dayNumber(battle.end) - dayNumber(battle.start) + 1;
}

// From and to are ISO dates; null leaves that side open.
export function overlaps(battle, from, to) {
  return (to === null || battle.start <= to) && (from === null || battle.end >= from);
}

export function activeOn(battles, isoDate) {
  return battles.filter((battle) => battle.start <= isoDate && isoDate <= battle.end);
}

export function durationText(battle) {
  const days = durationDays(battle);
  let text;
  if (days <= MAX_DAYS_IN_DAYS) {
    text = days === 1 ? "1 dag" : `${days} dagen`;
  } else if (days < MIN_DAYS_IN_YEARS) {
    text = `${Math.round(days / DAYS_PER_MONTH)} maanden`;
  } else {
    text = `${Math.round(days / DAYS_PER_YEAR)} jaar`;
  }
  return battle.precision === "month" ? `ongeveer ${text}` : text;
}

// The title to show: the English one a Veldslag of another language was given, else its own.
export function displayTitle(battle) {
  return battle.title_en || battle.title;
}

// The original title beside an English one, marked when a model translated it; null otherwise.
export function titleNote(battle) {
  if (!battle.title_en) return null;
  return battle.title_source === "vertaald" ? `${battle.title} (vertaald)` : battle.title;
}

export function filterBattles(battles, query) {
  const needle = query.trim().toLowerCase();
  if (needle === "") {
    return battles;
  }
  return battles.filter((battle) =>
    [battle.title, battle.title_en, battle.place, battle.part_of].some((field) => field != null && field.toLowerCase().includes(needle)),
  );
}

// The battles with no position at all (neither Wikipedia nor Eigen positie, so after
// applyPositions), active on the date (mode "date") or overlapping the period (mode
// "period"), matching the query. Without a selection, every date counts.
export function withoutPosition(battles, mode, selection, query) {
  let unplaced = battles.filter((battle) => battle.lat == null || battle.lng == null);
  if (selection) {
    unplaced = mode === "date" ? activeOn(unplaced, selection.date) : unplaced.filter((battle) => overlaps(battle, selection.from, selection.to));
  }
  return filterBattles(unplaced, query);
}

// Left and width as percentages of an axis from bounds.min to bounds.max (ISO dates).
export function barPosition(battle, bounds) {
  const first = dayNumber(bounds.min);
  const span = dayNumber(bounds.max) - first + 1;
  const start = Math.max(dayNumber(battle.start), first);
  const end = Math.min(dayNumber(battle.end), first + span - 1);
  const width = Math.min(100, Math.max(MIN_BAR_WIDTH, ((end - start + 1) / span) * 100));
  const left = Math.min(((start - first) / span) * 100, 100 - width);
  return { left: Math.max(0, left), width };
}

// viewBounds is { south, west, north, east }. Every battle in view is drawn, the longest
// first, so that shorter ones lie on top and stay clickable.
export function squaresToDraw(battles, viewBounds) {
  const inView = battles.filter((battle) => {
    const place = placeOf(battle);
    return place !== null && place.lat >= viewBounds.south && place.lat <= viewBounds.north
      && place.lng >= viewBounds.west && place.lng <= viewBounds.east;
  });
  inView.sort((a, b) => durationDays(b) - durationDays(a) || (a.title < b.title ? -1 : a.title > b.title ? 1 : 0));
  return inView;
}

// Names next to the squares are only readable when there are few or the map is zoomed in.
export function labelsToShow(squares, zoom) {
  return squares.length <= MAX_NAMED_SQUARES || zoom >= NAMED_FROM_ZOOM ? squares : [];
}

// The one axis every row's bar is drawn on.
export const AXIS_BOUNDS = { min: "1939-09-01", max: "1945-09-02" };

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

// Fraction (0 to 1) of the axis at which an ISO date lies; dates outside stick to the edge.
export function datePosition(isoDate, bounds) {
  const first = dayNumber(bounds.min);
  return clamp01((dayNumber(isoDate) - first) / (dayNumber(bounds.max) - first));
}

// The shaded part of the axis for a period; an open end reaches the edge.
export function bandPosition(from, to, bounds) {
  return {
    from: from === null ? 0 : datePosition(from, bounds),
    to: to === null ? 1 : datePosition(to, bounds),
  };
}

export function yearMarks(bounds) {
  const firstYear = Number(bounds.min.slice(0, 4));
  const lastYear = Number(bounds.max.slice(0, 4));
  const marks = [{ year: firstYear, fraction: 0 }];
  for (let year = firstYear + 1; year <= lastYear; year++) {
    const fraction = datePosition(`${year}-01-01`, bounds);
    if (fraction > 0 && fraction < 1) {
      marks.push({ year, fraction });
    }
  }
  return marks;
}

// Each battle gets its Eigen positie (hand-placed) when there is one; the file's own
// position stays available as wikiLat/wikiLng.
export function applyPositions(battles, positions) {
  const byTitle = new Map(positions.map((position) => [position.title, position]));
  return battles.map((battle) => {
    const own = byTitle.get(battle.title);
    const merged = { ...battle, wikiLat: battle.lat ?? null, wikiLng: battle.lng ?? null };
    return own ? { ...merged, lat: own.lat, lng: own.lng, own: true } : merged;
  });
}

// Each battle with Plaatshints gets its Voorzet, from the summary per title.
export function applyVoorzet(battles, summary) {
  return battles.map((battle) => {
    const found = summary[battle.title];
    return found?.voorzet_lat != null ? { ...battle, voorzet: { lat: found.voorzet_lat, lng: found.voorzet_lng } } : battle;
  });
}

// "Nog te verfijnen": only a Voorzet, no position from Wikipedia and no Eigen positie.
export function isRefining(battle) {
  return (battle.lat == null || battle.lng == null) && battle.voorzet != null;
}

// Where a battle stands on the map: its position, else its Voorzet, else nowhere (null).
export function placeOf(battle) {
  if (battle.lat != null && battle.lng != null) return { lat: battle.lat, lng: battle.lng };
  return battle.voorzet ?? null;
}

const EARTH_KM = 6371;
const toRad = (degrees) => (degrees * Math.PI) / 180;

// The great-circle distance in km between two { lat, lng }.
export function distanceKm(a, b) {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.sqrt(Math.min(1, h)));
}

// The Afwijking of a battle: km from where it stands on the map to the middle of its Plaatshints
// (the summary's lat and lng); null without hints or without a place.
export function afwijking(battle, summary) {
  const place = placeOf(battle);
  return summary && place ? distanceKm(place, summary) : null;
}

// The equivalent longitude in [-180, 180], for a marker dragged past the date line.
export function wrapLng(lng) {
  if (lng >= -180 && lng <= 180) {
    return lng;
  }
  return ((((lng + 180) % 360) + 360) % 360) - 180;
}

// The Kampen a Winnaar is made of, in the order of the extraction, with their names.
const KAMP_NAMES = { as: "As", westers: "Westerse geallieerden", sovjet: "Sovjet-Unie", overig: "Overig" };

function knownKampen(winner) {
  return Array.isArray(winner) ? winner.filter((kamp) => kamp in KAMP_NAMES).slice(0, 2) : [];
}

// The classes that colour a square or swatch: win1-<kamp>, and win2-<kamp> for the second
// Kamp of an undecided battle. No class leaves the colour of an unknown Winnaar.
export function winnerClasses(winner) {
  return knownKampen(winner).map((kamp, i) => `win${i + 1}-${kamp}`);
}

export function winnerText(winner) {
  const kampen = knownKampen(winner);
  if (kampen.length === 1) return `Winnaar: ${kampen[0] === "overig" ? "overig" : KAMP_NAMES[kampen[0]]}`;
  if (kampen.length === 2) return `Winnaar: onbeslist (${kampen.map((k) => KAMP_NAMES[k]).join(" – ")})`;
  return "Winnaar: onbekend";
}

export const WINNER_LEGEND = [
  ...Object.entries(KAMP_NAMES).map(([kamp, name]) => ({ name, classes: [`win1-${kamp}`] })),
  { name: "Onbeslist", classes: ["win1-as", "win2-westers"] },
  { name: "Onbekend", classes: [] },
];

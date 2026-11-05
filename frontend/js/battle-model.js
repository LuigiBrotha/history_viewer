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

export function filterBattles(battles, query) {
  const needle = query.trim().toLowerCase();
  if (needle === "") {
    return battles;
  }
  return battles.filter((battle) =>
    [battle.title, battle.place, battle.part_of].some((field) => field != null && field.toLowerCase().includes(needle)),
  );
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

// viewBounds is { south, west, north, east }. The longest battles stay when the cap bites.
export function squaresToDraw(battles, viewBounds, max) {
  const inView = battles.filter(
    (battle) =>
      battle.lat != null &&
      battle.lng != null &&
      battle.lat >= viewBounds.south &&
      battle.lat <= viewBounds.north &&
      battle.lng >= viewBounds.west &&
      battle.lng <= viewBounds.east,
  );
  inView.sort((a, b) => durationDays(b) - durationDays(a) || (a.title < b.title ? -1 : a.title > b.title ? 1 : 0));
  return inView.slice(0, max);
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

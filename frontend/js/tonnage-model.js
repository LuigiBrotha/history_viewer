import { writeView } from "./url-state.js";

const COUNTED_OUTCOMES = new Set(["sunk", "captured"]);
const DAY_MS = 24 * 60 * 60 * 1000;
// West of here and south of Greenland lie the American coasts, the Gulf and the Caribbean.
const AMERICAN_WEST_OF = -50;
const AMERICAN_SOUTH_OF = 52;
// English Wikipedia: "June 1940 – February 1941 (The Happy Time)" in Battle of the Atlantic,
// "January–August 1942" in Torpedo Alley.
export const HAPPY_TIMES = [
  { name: "First Happy Time", short: "1e", from: "1940-06-01", to: "1941-02-28" },
  { name: "Second Happy Time", short: "2e", from: "1942-01-01", to: "1942-08-31" },
];
const MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"];

export function formatNumber(value) {
  return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

// One series per boat: its sunk and captured ships in order, with the running total after
// each. uboat.net counts captured ships as lost too; damaged ships did not go down. Biggest first.
export function boatSeries(ships) {
  const byBoat = new Map();
  for (const ship of ships) {
    if (COUNTED_OUTCOMES.has(ship.outcome)) {
      if (!byBoat.has(ship.boat_slug)) {
        byBoat.set(ship.boat_slug, { slug: ship.boat_slug, number: ship.boat_number, hits: [] });
      }
      byBoat.get(ship.boat_slug).hits.push(ship);
    }
  }
  const series = [];
  for (const { slug, number, hits } of byBoat.values()) {
    hits.sort((a, b) => a.date.localeCompare(b.date));
    let total = 0;
    const steps = hits.map((hit) => {
      total += hit.tons;
      return { date: hit.date, total, tons: hit.tons, name: hit.name };
    });
    series.push({ slug, number, total, steps });
  }
  return series.sort((a, b) => b.total - a.total || a.slug.localeCompare(b.slug));
}

// Gives the biggest boats a colour slot. A boat keeps its slot for as long as the page is
// open: colour follows the boat, so new data never repaints the boats already shown.
export function colorSlots(series, slots, slotCount) {
  const used = new Set(slots.values());
  for (const { slug } of series) {
    if (used.size >= slotCount) {
      return;
    }
    if (!slots.has(slug)) {
      let slot = 0;
      while (used.has(slot)) {
        slot += 1;
      }
      slots.set(slug, slot);
      used.add(slot);
    }
  }
}

function isoDay(time) {
  return new Date(time).toISOString().slice(0, 10);
}

function periodStart(date, unit) {
  if (unit === "month") {
    return `${date.slice(0, 7)}-01`;
  }
  if (unit === "week") {
    const time = Date.parse(date);
    const daysSinceMonday = (new Date(time).getUTCDay() + 6) % 7;
    return isoDay(time - daysSinceMonday * DAY_MS);
  }
  return date;
}

function nextPeriod(period, unit) {
  if (unit === "month") {
    const start = new Date(Date.parse(period));
    return isoDay(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
  }
  return isoDay(Date.parse(period) + (unit === "week" ? 7 : 1) * DAY_MS);
}

// One bar per day, week or month from the first ship to the last, also when nothing sank;
// `span` ([first, last] date) sets a wider axis, so that a part of the ships can be compared.
// A bar stacks each boat's running total up to and including that period, biggest boat first;
// added and ships tell what that boat sank in the period itself.
export function stackedBars(series, unit, span = shipsSpan(series)) {
  if (span === null) {
    return [];
  }
  const dates = span;
  const last = periodStart(dates[dates.length - 1], unit);
  const cursors = series.map(() => 0);
  const bars = [];
  for (let period = periodStart(dates[0], unit); period <= last; period = nextPeriod(period, unit)) {
    const next = nextPeriod(period, unit);
    const segments = [];
    let height = 0;
    series.forEach((line, index) => {
      const ships = [];
      let added = 0;
      while (cursors[index] < line.steps.length && line.steps[cursors[index]].date < next) {
        const step = line.steps[cursors[index]];
        ships.push(step.name);
        added += step.tons;
        cursors[index] += 1;
      }
      if (cursors[index] > 0) {
        const to = height + line.steps[cursors[index] - 1].total;
        segments.push({ slug: line.slug, number: line.number, from: height, to, added, ships });
        height = to;
      }
    });
    bars.push({ period, total: height, segments });
  }
  return bars;
}

function shipsSpan(series) {
  if (series.length === 0) {
    return null;
  }
  const dates = series.flatMap(({ steps }) => [steps[0].date, steps[steps.length - 1].date]).sort();
  return [dates[0], dates[dates.length - 1]];
}

// The same bars with only what sank in each period itself.
export function periodBars(bars) {
  return bars.map(({ period, segments }) => {
    let height = 0;
    const kept = [];
    for (const segment of segments) {
      if (segment.added > 0) {
        kept.push({ ...segment, from: height, to: height + segment.added });
        height += segment.added;
      }
    }
    return { period, total: height, segments: kept };
  });
}

// How many U-boat days at sea each period has, under its periodStart.
export function atSeaDays(patrols, unit) {
  const days = new Map();
  for (const { departure_date: departure, arrival_date: arrival } of patrols) {
    const last = Date.parse(arrival);
    for (let time = Date.parse(departure); time <= last; time += DAY_MS) {
      const period = periodStart(isoDay(time), unit);
      days.set(period, (days.get(period) ?? 0) + 1);
    }
  }
  return days;
}

// Tons per U-boat per day at sea: what made the Happy Times, more than the tonnage itself.
export function ratePerBoatDay(bars, boatDays) {
  return bars.map(({ period, total, segments }) => {
    const days = boatDays.get(period) ?? 0;
    if (days === 0) {
      return { period, total: 0, boatDays: 0, segments: [] };
    }
    return {
      period,
      total: total / days,
      boatDays: days,
      segments: segments.map((segment) => ({ ...segment, from: segment.from / days, to: segment.to / days })),
    };
  });
}

export function inAmericanWaters({ lat, lng }) {
  return lat != null && lng != null && lng < AMERICAN_WEST_OF && lat < AMERICAN_SOUTH_OF;
}

// The bars of a view of the chart.
export function barsFor(view, { ships, series, periods, unit }) {
  if (view === "amerika") {
    return periodBars(stackedBars(boatSeries(ships.filter(inAmericanWaters)), unit, shipsSpan(series)));
  }
  const bars = stackedBars(series, unit);
  if (view === "cumulatief") {
    return bars;
  }
  return view === "rendement" ? ratePerBoatDay(periodBars(bars), atSeaDays(periods, unit)) : periodBars(bars);
}

function overlaps(period, unit, { from, to }) {
  return period <= to && nextPeriod(period, unit) > from;
}

// Where each Happy Time lies on the axis, as the indexes of its first and last bar.
export function happyTimeSpans(bars, unit) {
  return HAPPY_TIMES.flatMap((time) => {
    const inside = bars.flatMap(({ period }, index) => (overlaps(period, unit, time) ? [index] : []));
    return inside.length === 0 ? [] : [{ ...time, first: inside[0], last: inside[inside.length - 1] }];
  });
}

export function happyTimeOf(period, unit) {
  return HAPPY_TIMES.find((time) => overlaps(period, unit, time)) ?? null;
}

// Every hit is a dot, the damaged ships too; the view of American waters only shows those there.
export function shipDots(ships, view) {
  return view === "amerika" ? ships.filter(inAmericanWaters) : ships;
}

// Where a date lies on the axis of the bars, in bars: the index of its bar plus how far through
// that bar it is. A date outside the bars stays at the edge; null without bars.
export function barPosition(date, bars, unit) {
  if (bars.length === 0) {
    return null;
  }
  if (date < bars[0].period) {
    return 0;
  }
  let low = 0;
  let high = bars.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (bars[middle].period <= date) {
      low = middle;
    } else {
      high = middle - 1;
    }
  }
  const start = Date.parse(bars[low].period);
  const end = Date.parse(nextPeriod(bars[low].period, unit));
  return low + Math.min(1, (Date.parse(date) - start) / (end - start));
}

// The dot nearest to (x, y) within reach, or null.
export function dotAt(dots, x, y, reach) {
  let best = null;
  let bestDistance = reach * reach;
  for (const dot of dots) {
    const distance = (dot.x - x) ** 2 + (dot.y - y) ** 2;
    if (distance <= bestDistance) {
      best = dot;
      bestDistance = distance;
    }
  }
  return best;
}

// The Tijdlijn on the date of this hit, with the Artikel of the ship.
export function shipLink(ship) {
  return `dag-tot-dag${writeView({ date: ship.date, ship: ship.ship_external_id }, "date")}`;
}

const OUTCOME_LABELS = { sunk: "Gezonken", captured: "Buitgemaakt", damaged: "Beschadigd" };

export function outcomeLabel(outcome) {
  return OUTCOME_LABELS[outcome] ?? outcome;
}

export function segmentAt(bar, tons) {
  return bar.segments.find((segment) => tons >= segment.from && tons < segment.to) ?? null;
}

export function periodLabel(period, unit) {
  const [year, month, day] = period.split("-").map(Number);
  const monthYear = `${MONTHS[month - 1]} ${year}`;
  if (unit === "month") {
    return monthYear;
  }
  return unit === "week" ? `week van ${day} ${monthYear}` : `${day} ${monthYear}`;
}

export function niceMax(value) {
  if (value <= 0) {
    return 1000;
  }
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const factor of [1, 2, 3, 4, 5, 6, 8, 10]) {
    if (factor * magnitude >= value) {
      return factor * magnitude;
    }
  }
  return 10 * magnitude;
}

export function tableRows(series) {
  return series.map(({ slug, number, total, steps }) => ({
    slug,
    boat: number,
    tons: formatNumber(total),
    ships: steps.length,
  }));
}

function normalized(text) {
  return text.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function matchSeries(series, query) {
  const wanted = normalized(query);
  if (wanted === "") {
    return null;
  }
  const digits = (text) => text.replace(/\D/g, "");
  return (
    series.find((candidate) => normalized(candidate.number) === wanted) ??
    series.find((candidate) => digits(candidate.number) === wanted) ??
    series.find((candidate) => normalized(candidate.number).includes(wanted)) ??
    null
  );
}

export function formatTons(value) {
  return `${formatNumber(value)} ton`;
}

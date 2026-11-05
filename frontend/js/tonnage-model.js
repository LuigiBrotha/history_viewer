const COUNTED_OUTCOMES = new Set(["sunk", "captured"]);
const DAY_MS = 24 * 60 * 60 * 1000;
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

// One bar per day, week or month from the first ship to the last, also when nothing sank.
// A bar stacks each boat's running total up to and including that period, biggest boat first;
// added and ships tell what that boat sank in the period itself.
export function stackedBars(series, unit) {
  if (series.length === 0) {
    return [];
  }
  const dates = series.flatMap(({ steps }) => [steps[0].date, steps[steps.length - 1].date]).sort();
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

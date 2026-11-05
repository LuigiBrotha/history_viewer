const COUNTED_OUTCOMES = new Set(["sunk", "captured"]);

function dutchNumber(value) {
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

export function tonsOn(series, date) {
  let tons = 0;
  for (const step of series.steps) {
    if (step.date > date) {
      break;
    }
    tons = step.total;
  }
  return tons;
}

export function nearestSeries(series, date, tons) {
  let best = null;
  let bestDistance = Infinity;
  for (const candidate of series) {
    const distance = Math.abs(tonsOn(candidate, date) - tons);
    if (distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }
  return best;
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
    tons: dutchNumber(total),
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
  return `${dutchNumber(value)} ton`;
}

const OUTCOME_TEXT = { sunk: "gezonken", damaged: "beschadigd", captured: "buitgemaakt" };
const DARK = "#222222";
const PURPLE = "#7a3db8";

function shipKey(ship) {
  return `${ship.ship_external_id}|${ship.boat_slug}|${ship.date}`;
}

// A ship can be hit more than once, so the key holds the boat and the date too.
export function mergeShips(ships, changed) {
  const byKey = new Map(changed.map((ship) => [shipKey(ship), ship]));
  const seen = new Set();
  const merged = ships.map((ship) => {
    const key = shipKey(ship);
    if (byKey.has(key)) {
      seen.add(key);
      return byKey.get(key);
    }
    return ship;
  });
  for (const ship of changed) {
    const key = shipKey(ship);
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(ship);
    }
  }
  return merged;
}

// date is the timeline's Date; a ship counts from its own date on.
export function shipsUpToDate(ships, date, followedSlug = null) {
  const day = date.toISOString().slice(0, 10);
  return ships.filter((ship) => ship.date <= day && (followedSlug === null || ship.boat_slug === followedSlug));
}

// from and to are ISO dates or null (open ended).
export function shipsInPeriod(ships, from, to) {
  return ships.filter((ship) => (from === null || ship.date >= from) && (to === null || ship.date <= to));
}

export function shipsWithoutPosition(ships) {
  return ships.filter((ship) => ship.lat == null || ship.lng == null);
}

// Dutch grouping by hand: Intl leaves four-digit numbers ungrouped.
function dutchNumber(value) {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export function shipTotalsLine(ships) {
  const parts = [];
  for (const outcome of ["sunk", "damaged", "captured"]) {
    const hits = ships.filter((ship) => ship.outcome === outcome);
    if (hits.length > 0) {
      const tons = hits.reduce((sum, ship) => sum + ship.tons, 0);
      parts.push(`${hits.length} ${OUTCOME_TEXT[outcome]} (${dutchNumber(tons)} ton)`);
    }
  }
  return parts.join(" · ");
}

export function shipTooltip(ship) {
  const by = ship.outcome === "sunk" ? "gezonken door" : `${OUTCOME_TEXT[ship.outcome]} door`;
  return `${ship.name} — ${dutchNumber(ship.tons)} ton — ${by} ${ship.boat_number} op ${ship.date}`;
}

export function shipStyle(outcome) {
  if (outcome === "damaged") {
    return { color: DARK, fillColor: DARK, fillOpacity: 0 };
  }
  const color = outcome === "captured" ? PURPLE : DARK;
  return { color, fillColor: color, fillOpacity: 1 };
}

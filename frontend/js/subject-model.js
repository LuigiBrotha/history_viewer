import { OUTCOME_TEXT, dutchNumber } from "./boat-panel.js";
import { patrolStart } from "./status-map.js";

const naturally = (a, b) => a.localeCompare(b, "en", { numeric: true });

function boatMeta(boat) {
  const count = boat.patrol_count ?? 0;
  const parts = [boat.type, `${count} ${count === 1 ? "patrouille" : "patrouilles"}`];
  if (boat.tonnage > 0) parts.push(`${dutchNumber(boat.tonnage)} ton`);
  return parts.filter(Boolean).join(" · ");
}

// The rows of the U-boten list: on number, so that U-9 comes before U-10.
export function boatSubjects(boats) {
  return [...boats]
    .sort((a, b) => naturally(a.number, b.number))
    .map((boat) => ({
      key: boat.slug,
      title: boat.number,
      meta: boatMeta(boat),
      search: [boat.number, boat.type].filter(Boolean).join(" ").toLowerCase(),
    }));
}

function shipMeta(hits) {
  const last = hits[hits.length - 1];
  const parts = [hits[0].date, `${dutchNumber(Math.max(...hits.map((hit) => hit.tons)))} ton`, OUTCOME_TEXT[last.outcome]];
  if (hits.length > 1) parts.push(`${hits.length} treffers`);
  return parts.join(" · ");
}

// The rows of the Schepen list: one per Schip, however often it was hit, on the date of the
// first Scheepstreffer.
export function shipSubjects(allHits) {
  const byShip = new Map();
  for (const hit of allHits) {
    if (!byShip.has(hit.ship_external_id)) byShip.set(hit.ship_external_id, []);
    byShip.get(hit.ship_external_id).push(hit);
  }
  const rows = [...byShip.entries()].map(([key, hits]) => {
    const ordered = [...hits].sort((a, b) => a.date.localeCompare(b.date));
    return { key, title: ordered[0].name, meta: shipMeta(ordered), search: ordered[0].name.toLowerCase(), hits: ordered };
  });
  return rows.sort((a, b) => a.hits[0].date.localeCompare(b.hits[0].date) || naturally(a.title, b.title));
}

export function hitByDate(ship, isoDate) {
  return ship.hits.some((hit) => hit.date <= isoDate);
}

// from and to are ISO dates or null (open ended).
export function hitInPeriod(ship, from, to) {
  return ship.hits.some((hit) => (from === null || hit.date >= from) && (to === null || hit.date <= to));
}

// The oldest date any of these patrols began on, or null when none has one.
export function firstPatrolDate(patrols) {
  return patrols.map(patrolStart).filter((date) => date !== null).sort()[0] ?? null;
}

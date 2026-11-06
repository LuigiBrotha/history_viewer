const MAX_ROWS = 5;

const needle = (q) => (q ?? "").trim().toLowerCase();
const has = (field, n) => field != null && String(field).toLowerCase().includes(n);

function pick(items, q, fields, toRow, seenKey = null) {
  const n = needle(q);
  if (!n) return [];
  const rows = [];
  const seen = new Set();
  for (const item of items) {
    if (!fields.some((field) => has(item[field], n))) continue;
    if (seenKey) {
      if (seen.has(item[seenKey])) continue;
      seen.add(item[seenKey]);
    }
    rows.push(toRow(item));
    if (rows.length === MAX_ROWS) break;
  }
  return rows;
}

export const matchBoats = (boats, q) =>
  pick(boats, q, ["number", "name"], (boat) => ({ label: boat.number, sub: boat.name ?? null, item: boat }));

export const matchShips = (ships, q) =>
  pick(ships, q, ["name"], (ship) => ({ label: ship.name, sub: ship.boat_number ?? null, item: ship }), "ship_external_id");

export const matchBattles = (battles, q) =>
  pick(battles, q, ["title", "place"], (battle) => ({ label: battle.title, sub: battle.place ?? null, item: battle }));

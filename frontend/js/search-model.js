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
  pick(battles, q, ["title", "title_en", "place"], (battle) => ({
    label: battle.title_en || battle.title,
    sub: [battle.title_en ? battle.title : null, battle.place].filter(Boolean).join(" · ") || null,
    item: battle,
  }));

const ROUND = 1e5;
const DECIMAL_PAIR = /^([-+]?\d+(?:\.\d+)?)\s*(?:,\s*|\s+)([-+]?\d+(?:\.\d+)?)$/;
const ONLY_COORDINATE_CHARACTERS = /^[\d.,\s°'′"″NSEWnsew+-]+$/;

function round(value) {
  return Math.round(value * ROUND) / ROUND;
}

function inRange(lat, lng) {
  return Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? { lat: round(lat), lng: round(lng) } : null;
}

function degrees(numbers) {
  if (numbers.length < 1 || numbers.length > 3 || numbers.slice(1).some((n) => n >= 60)) return null;
  return numbers.reduce((sum, n, i) => sum + n / 60 ** i, 0);
}

// A position typed or pasted into the search field: "52.37, 4.89", "51°59′N 5°55′E" or
// "N 52.5 E 13.4". Anything else, or a position off the globe, is null.
export function parseCoordinates(text) {
  const trimmed = String(text ?? "").trim();
  if (!trimmed || !ONLY_COORDINATE_CHARACTERS.test(trimmed)) return null;
  const pair = trimmed.match(DECIMAL_PAIR);
  if (pair) return inRange(Number(pair[1]), Number(pair[2]));
  const tokens = trimmed.toUpperCase().match(/\d+(?:\.\d+)?|[NSEW]/g) ?? [];
  const letters = tokens.filter((t) => /^[NSEW]$/.test(t));
  if (letters.length !== 2) return null;
  const before = /^[NSEW]$/.test(tokens[0]);
  const groups = [];
  let current = [];
  for (const token of tokens) {
    if (/^[NSEW]$/.test(token)) {
      if (before) {
        if (current.length) groups.push(current);
        current = [token];
      } else {
        groups.push([token, ...current]);
        current = [];
      }
    } else {
      current.push(token);
    }
  }
  if (before && current.length) groups.push(current);
  if (groups.length !== 2 || !"NS".includes(groups[0][0]) || !"EW".includes(groups[1][0])) return null;
  const [lat, lng] = groups.map(([letter, ...numbers]) => {
    const value = degrees(numbers.map(Number));
    return value === null ? null : letter === "S" || letter === "W" ? -value : value;
  });
  return lat === null || lng === null ? null : inRange(lat, lng);
}

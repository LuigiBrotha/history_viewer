// The view of a page (date or period, Veldslag, Gevolgde boot, Kaartuitsnede, Alleen zonder
// positie) as a URL search string. Pure: no DOM, no history; the pages decide when to read and write.

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const BOAT_PATTERN = /^[a-z0-9-]+$/;
const MAP_DECIMALS = 4;
const MAX_ZOOM = 18;
// The sort orders other than the default (by date).
const SORTS = new Set(["naam", "duur", "verfijnen"]);

function validDate(text) {
  if (!text || !DATE_PATTERN.test(text)) return undefined;
  const parsed = new Date(`${text}T00:00:00Z`);
  const real = !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === text;
  return real ? text : undefined;
}

function validBoat(text) {
  return text && BOAT_PATTERN.test(text) ? text : undefined;
}

function validBattle(text) {
  return text ? text.replaceAll("_", " ") : undefined;
}

function validMap(text) {
  if (!text) return undefined;
  const parts = text.split(",");
  if (parts.length !== 3 || parts.some((part) => part.trim() === "")) return undefined;
  const [lat, lng, zoom] = parts.map(Number);
  if (![lat, lng, zoom].every(Number.isFinite)) return undefined;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return undefined;
  if (!Number.isInteger(zoom) || zoom < 1 || zoom > MAX_ZOOM) return undefined;
  return { lat, lng, zoom };
}

export function readView(search, kind) {
  const params = new URLSearchParams(search);
  const fields =
    kind === "period"
      ? [
          ["from", validDate(params.get("van"))],
          ["to", validDate(params.get("tot"))],
        ]
      : [["date", validDate(params.get("datum"))]];
  fields.push(
    ["battle", validBattle(params.get("veldslag"))],
    ["boat", validBoat(params.get("boot"))],
    ["map", validMap(params.get("kaart"))],
    ["nopos", params.get("zonderpositie") === "1" ? true : undefined],
    ["filter", params.get("filter") || undefined],
    ["sort", SORTS.has(params.get("sorteer")) ? params.get("sorteer") : undefined],
    ["labelMode", params.get("filtermodus") === "of" ? "of" : undefined],
    ["showAll", params.get("alles") === "1" ? true : undefined],
    ["version", params.get("artikel") === "nl" ? "nl" : undefined],
    ["routesOff", params.get("routes") === "uit" ? true : undefined],
    ["spread", /^\d+-\d*$/.test(params.get("spreiding") ?? "") ? params.get("spreiding") : undefined],
  );
  return Object.fromEntries(fields.filter(([, value]) => value !== undefined));
}

export function writeView(view, kind) {
  const pairs = [];
  const add = (name, value) => {
    if (value) pairs.push(`${name}=${value}`);
  };
  const encode = (text) => new URLSearchParams({ v: text }).toString().slice(2);
  if (kind === "period") {
    add("van", view.from && encode(view.from));
    add("tot", view.to && encode(view.to));
  } else {
    add("datum", view.date && encode(view.date));
  }
  add("veldslag", view.battle && encode(view.battle.replaceAll(" ", "_")));
  add("boot", view.boat && encode(view.boat));
  if (view.map) {
    const { lat, lng, zoom } = view.map;
    add("kaart", `${lat.toFixed(MAP_DECIMALS)},${lng.toFixed(MAP_DECIMALS)},${zoom}`);
  }
  add("zonderpositie", view.nopos === true && "1");
  add("filter", view.filter && encode(view.filter));
  add("sorteer", SORTS.has(view.sort) && view.sort);
  add("filtermodus", view.labelMode === "of" && "of");
  add("alles", view.showAll === true && "1");
  add("routes", view.routesOff === true && "uit");
  add("spreiding", view.spread && encode(view.spread));
  add("artikel", view.version === "nl" && "nl");
  return pairs.length ? `?${pairs.join("&")}` : "";
}

// What a link to another map page carries: not the date or period, which are per page.
export function carriedView(view) {
  const { battle, boat, map, nopos, filter, sort, labelMode, showAll, spread, version, routesOff } = view;
  return Object.fromEntries(
    Object.entries({ battle, boat, map, nopos, filter, sort, labelMode, showAll, spread, version, routesOff }).filter(([, value]) => value !== undefined),
  );
}

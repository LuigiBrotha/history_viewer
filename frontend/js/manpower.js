// Manschappen along a Spoor: soldiers plus the crews of tanks and aircraft.

export const DEFAULT_MAX_WIDTH = 48;
export const MIN_BAND_WIDTH = 8;
export const MAX_BAND_WIDTH = 96;

// The width in px from a number or numeric string: a whole number from 8 to 96, else undefined.
export function clampBandWidth(value) {
  if (value === null || value === undefined || (typeof value === "string" && value.trim() === "")) return undefined;
  const number = Number(value);
  return Number.isInteger(number) && number >= MIN_BAND_WIDTH && number <= MAX_BAND_WIDTH ? number : undefined;
}

const crewOf = (items) => (items || []).reduce((sum, i) => sum + i.aantal * i.bemanning, 0);
const fmt = (n) => n.toLocaleString("nl-NL");

function own(entry) {
  if (entry.soldaten == null) return null;
  const tanks = crewOf(entry.tanks);
  const aircraft = crewOf(entry.vliegtuigen);
  return { total: entry.soldaten + tanks + aircraft, soldiers: entry.soldaten, tanks, aircraft, borrowedFrom: null };
}

export function manpowerOf(title, table) {
  const entry = table[title];
  if (!entry) return null;
  if (!entry.overgenomen_van) return own(entry);
  const lender = table[entry.overgenomen_van];
  const figure = lender ? own(lender) : null;
  return figure && { ...figure, borrowedFrom: entry.overgenomen_van };
}

export function lossesOf(title, table) {
  const lost = table[title]?.verliezen;
  if (!lost) return null;
  return (lost.manschappen || 0) + crewOf(lost.tanks) + crewOf(lost.vliegtuigen);
}

export function bandStops(battles, table) {
  return battles.map((battle) => ({
    battle,
    manpower: manpowerOf(battle.title, table),
    loss: lossesOf(battle.title, table),
    entry: table[battle.title] || null,
  }));
}

export function bandSteps(stops) {
  return stops.slice(1).map((to, i) => {
    const from = stops[i];
    return { from, to, solid: from.manpower != null && to.manpower != null };
  });
}

export function highestManpower(stops) {
  return stops.reduce((max, s) => Math.max(max, s.manpower ? s.manpower.total : 0), 0);
}

export function widthOf(manpower, highest, maxPx) {
  return highest === 0 ? 0 : (manpower / highest) * maxPx;
}

function buildUp(stop) {
  const { manpower, entry } = stop;
  const lines = [`${fmt(manpower.soldiers)} soldaten`];
  if (manpower.borrowedFrom) {
    if (manpower.tanks) lines.push(`${fmt(manpower.tanks)} bemanning van tanks`);
    if (manpower.aircraft) lines.push(`${fmt(manpower.aircraft)} bemanning van vliegtuigen`);
    return lines;
  }
  for (const t of entry.tanks || []) lines.push(`${fmt(t.aantal)} tanks × ${t.bemanning}`);
  for (const v of entry.vliegtuigen || []) lines.push(`${fmt(v.aantal)} vliegtuigen × ${v.bemanning}`);
  return lines;
}

export function stopText(stop) {
  const { battle, manpower, loss, entry } = stop;
  const lines = [battle.title_en || battle.title];
  if (!manpower) {
    lines.push("Geen aantal soldaten");
  } else {
    lines.push(`${fmt(manpower.total)} Manschappen`, ...buildUp(stop), "Hele kant, niet alleen de eigen troepen");
    if (loss != null) lines.push(`Verlies: ${fmt(loss)}`);
    if (manpower.borrowedFrom) lines.push(`cijfer van ${manpower.borrowedFrom}`);
  }
  if (entry && entry.tekst) lines.push(entry.tekst);
  return lines.join("\n");
}

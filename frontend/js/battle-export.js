// Export of the listed Veldslagen (CSV, GeoJSON) and a back-up of the Eigen posities. Pure:
// the pane turns the text into a download.

const CSV_COLUMNS = [
  ["titel", (b) => b.title],
  ["taal", (b) => b.lang ?? "en"],
  ["begin", (b) => b.start],
  ["einde", (b) => b.end],
  ["breedte", (b) => b.lat ?? ""],
  ["lengte", (b) => b.lng ?? ""],
  ["eigen_positie", (b) => (b.own ? "ja" : "nee")],
  ["plaats", (b) => b.place ?? ""],
  ["winnaar", (b) => (b.winner ?? []).join("+")],
  ["landen", (b) => (b.countries ?? []).join("; ")],
  ["bevelhebbers", (b) => (b.commanders ?? []).join("; ")],
  ["eenheden", (b) => (b.units ?? []).join("; ")],
  ["url", (b) => b.url ?? ""],
];

function csvCell(value) {
  const text = String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function toCsv(battles) {
  const lines = [CSV_COLUMNS.map(([name]) => name).join(",")];
  for (const battle of battles) lines.push(CSV_COLUMNS.map(([, value]) => csvCell(value(battle))).join(","));
  return `${lines.join("\r\n")}\r\n`;
}

export function toGeoJson(battles) {
  const features = battles
    .filter((b) => b.lat != null && b.lng != null)
    .map((b) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [b.lng, b.lat] },
      properties: {
        titel: b.title, taal: b.lang ?? "en", begin: b.start, einde: b.end, eigen_positie: Boolean(b.own),
        plaats: b.place ?? null, winnaar: b.winner ?? [], landen: b.countries ?? [],
        bevelhebbers: b.commanders ?? [], eenheden: b.units ?? [], url: b.url ?? null,
      },
    }));
  return JSON.stringify({ type: "FeatureCollection", features }, null, 1);
}

export function backupText(positions) {
  const kept = positions.map(({ title, lat, lng }) => ({ title, lat, lng }));
  return JSON.stringify({ soort: "eigen-posities", positions: kept }, null, 1);
}

// The positions of a back-up file; throws on anything that is not one.
export function readBackup(text) {
  const data = JSON.parse(text);
  if (!data || !Array.isArray(data.positions)) throw new Error("Geen back-up van Eigen posities.");
  return data.positions.map(({ title, lat, lng }) => {
    if (typeof title !== "string" || !title || !Number.isFinite(lat) || !Number.isFinite(lng)
      || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      throw new Error("Ongeldige positie in de back-up.");
    }
    return { title, lat, lng };
  });
}

// What restoring a back-up does: the back-up wins where it differs; positions it lacks stay.
export function restorePlan(current, backup) {
  const now = new Map(current.map((p) => [p.title, p]));
  const set = [];
  let unchanged = 0;
  for (const position of backup) {
    const existing = now.get(position.title);
    if (existing && existing.lat === position.lat && existing.lng === position.lng) unchanged += 1;
    else set.push(position);
  }
  return { set, unchanged };
}

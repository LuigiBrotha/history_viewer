const REQUEST_TIMEOUT_MS = 30000;
// A full load carries every patrol and takes much longer than an incremental one.
const FULL_LOAD_TIMEOUT_MS = 120000;

export async function fetchBoats() {
  const response = await fetch("api/uboats/boten");
  if (!response.ok) {
    throw new Error(`Failed to fetch boats: ${response.status}`);
  }
  return response.json();
}

export async function fetchRoutes(since = null) {
  const query = since ? `?since=${encodeURIComponent(since)}` : "";
  const response = await fetch(`api/uboats/routes${query}`, { signal: AbortSignal.timeout(since ? REQUEST_TIMEOUT_MS : FULL_LOAD_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to fetch routes: ${response.status}`);
  }
  return response.json();
}

// The patrols come in order of departure, so this many reach to about the end of the first year.
const FIRST_PAGE_SIZE = 350;
const ROUTES_PAGE_SIZE = 500;

// Reads every patrol page by page. onPage(page, last) can draw each page as it arrives, so the
// map starts with the first year while the rest still comes in.
export async function fetchAllRoutes({ firstPageSize = FIRST_PAGE_SIZE, pageSize = ROUTES_PAGE_SIZE, onProgress = () => {}, onPage = () => {} } = {}) {
  const routes = [];
  let size = firstPageSize;
  for (;;) {
    const response = await fetch(`api/uboats/routes?limit=${size}&offset=${routes.length}`, {
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch routes: ${response.status}`);
    }
    const page = await response.json();
    routes.push(...page);
    onProgress(routes.length);
    const last = page.length < size;
    onPage(page, last);
    if (last) {
      return routes;
    }
    size = pageSize;
  }
}

// The Onderwerpen whose text holds these words: { available, battles, boats, ships }, best first.
export async function fetchSearch(query) {
  const response = await fetch(`api/search?q=${encodeURIComponent(query)}`, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to search: ${response.status}`);
  }
  return response.json();
}

export async function fetchPatrolPeriods() {
  const response = await fetch("api/uboats/patrol-periods", { signal: AbortSignal.timeout(FULL_LOAD_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to fetch patrol periods: ${response.status}`);
  }
  return response.json();
}

export async function fetchShips(since = null) {
  const query = since ? `?since=${encodeURIComponent(since)}` : "";
  const response = await fetch(`api/uboats/ships${query}`, { signal: AbortSignal.timeout(since ? REQUEST_TIMEOUT_MS : FULL_LOAD_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to fetch ships: ${response.status}`);
  }
  return response.json();
}

export async function fetchStatus() {
  const response = await fetch("api/uboats/status", { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to fetch status: ${response.status}`);
  }
  return response.json();
}

export function canEdit(status) {
  return status?.can_edit === true;
}

const LAST_POINT = "Dit is het laatste punt van deze patrouille.";
const EDIT_TIMEOUT = "Dit duurt lang en wordt mogelijk nog verwerkt.";

// The only errors whose message may reach the user: everything else is logged.
export class EditError extends Error {}

async function editPoint(method, externalId, sequence, failure) {
  let response;
  try {
    // The first edit may load land data, so it gets as long as a full load.
    response = await fetch(`api/uboats/routes/${encodeURIComponent(externalId)}/excluded-points`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sequence }),
      signal: AbortSignal.timeout(FULL_LOAD_TIMEOUT_MS),
    });
  } catch (error) {
    console.error(error);
    throw new EditError(error?.name === "TimeoutError" ? EDIT_TIMEOUT : failure);
  }
  if (!response.ok) {
    if (response.status === 409) {
      throw new EditError(LAST_POINT);
    }
    let detail = null;
    try {
      detail = (await response.json()).detail;
    } catch {
      // No JSON body: nothing more to log.
    }
    console.error(`${method} excluded-points failed with ${response.status}`, detail);
    throw new EditError(failure);
  }
  try {
    return await response.json();
  } catch (error) {
    console.error(error);
    throw new EditError(failure);
  }
}

export function excludePoint(externalId, sequence) {
  return editPoint("POST", externalId, sequence, "Uitsluiten mislukt");
}

export function restorePoint(externalId, sequence) {
  return editPoint("DELETE", externalId, sequence, "Herstellen mislukt");
}

// A Dutch version may first have to be translated, which takes up to a few minutes.
const TRANSLATION_TIMEOUT_MS = 300000;

function versionRequest(version) {
  return {
    query: version === "nl" ? "?versie=nl" : "",
    signal: AbortSignal.timeout(version === "nl" ? TRANSLATION_TIMEOUT_MS : REQUEST_TIMEOUT_MS),
  };
}

export async function fetchBoat(slug, version = "origineel") {
  const { query, signal } = versionRequest(version);
  const response = await fetch(`api/uboats/boten/${encodeURIComponent(slug)}${query}`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch boat: ${response.status}`);
  }
  return response.json();
}

export async function fetchShip(shipExternalId, version = "origineel") {
  const { query, signal } = versionRequest(version);
  const response = await fetch(`api/uboats/ships/${encodeURIComponent(shipExternalId)}${query}`, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch ship: ${response.status}`);
  }
  return response.json();
}

export async function fetchBattlePositions() {
  const response = await fetch("api/battles/positions", { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to fetch battle positions: ${response.status}`);
  }
  return response.json();
}

export async function saveBattlePosition(title, lat, lng) {
  const response = await fetch(`api/battles/positions/${encodeURIComponent(title)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng }),
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`Failed to save battle position: ${response.status}`);
  }
  return response.json();
}

export async function clearBattlePosition(title) {
  const response = await fetch(`api/battles/positions/${encodeURIComponent(title)}`, {
    method: "DELETE",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`Failed to clear battle position: ${response.status}`);
  }
}

// The sanitised article of a battle in its language, or with version "nl" its Dutch version;
// null when there is none.
export async function fetchArticle(title, lang = "en", version = "origineel") {
  const params = new URLSearchParams();
  if (lang !== "en") params.set("lang", lang);
  if (version === "nl") params.set("versie", "nl");
  const query = params.size ? `?${params}` : "";
  const response = await fetch(`api/battles/articles/${encodeURIComponent(title)}${query}`, {
    signal: AbortSignal.timeout(version === "nl" ? TRANSLATION_TIMEOUT_MS : REQUEST_TIMEOUT_MS),
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Failed to fetch article: ${response.status}`);
  }
  return response.json();
}

// The Plaatshints of a battle: [{ name, lat, lng, kind }], none when it has none.
export async function fetchHints(title) {
  const response = await fetch(`api/battles/hints/${encodeURIComponent(title)}`, {
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch plaatshints: ${response.status}`);
  }
  return (await response.json()).hints;
}

// Per battle with Plaatshints: { count, lat, lng, spread_km } (their middle and spread).
export async function fetchHintSummary() {
  const response = await fetch("api/battles/hint-summary", { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`Failed to fetch the plaatshints summary: ${response.status}`);
  }
  return response.json();
}

// Places come from Nominatim through the backend. The caller's signal cancels a stale lookup.
export async function fetchPlaces(query, { signal } = {}) {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  const response = await fetch(`api/places?q=${encodeURIComponent(query)}`, {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch places: ${response.status}`);
  }
  return response.json();
}

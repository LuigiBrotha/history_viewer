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

const ROUTES_PAGE_SIZE = 250;

// Reads every patrol page by page, so that a loading indicator can show real progress.
export async function fetchAllRoutes({ pageSize = ROUTES_PAGE_SIZE, onProgress = () => {} } = {}) {
  const routes = [];
  for (;;) {
    const response = await fetch(`api/uboats/routes?limit=${pageSize}&offset=${routes.length}`, {
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch routes: ${response.status}`);
    }
    const page = await response.json();
    routes.push(...page);
    onProgress(routes.length);
    if (page.length < pageSize) {
      return routes;
    }
  }
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

export async function fetchBoat(slug) {
  const response = await fetch(`api/uboats/boten/${encodeURIComponent(slug)}`, {
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch boat: ${response.status}`);
  }
  return response.json();
}

export async function fetchShip(shipExternalId) {
  const response = await fetch(`api/uboats/ships/${encodeURIComponent(shipExternalId)}`, {
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
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

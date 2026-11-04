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

export async function fetchBoats() {
  const response = await fetch("api/uboats/boten");
  if (!response.ok) {
    throw new Error(`Failed to fetch boats: ${response.status}`);
  }
  return response.json();
}

export async function fetchRoutes(since = null) {
  const query = since ? `?since=${encodeURIComponent(since)}` : "";
  const response = await fetch(`api/uboats/routes${query}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch routes: ${response.status}`);
  }
  return response.json();
}

export async function fetchStatus() {
  const response = await fetch("api/uboats/status");
  if (!response.ok) {
    throw new Error(`Failed to fetch status: ${response.status}`);
  }
  return response.json();
}

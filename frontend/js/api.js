const API_BASE = "http://localhost:8000";

export async function fetchBoats() {
  const response = await fetch(`${API_BASE}/api/uboats/boten`);
  if (!response.ok) {
    throw new Error(`Failed to fetch boats: ${response.status}`);
  }
  return response.json();
}

export async function fetchRoutes() {
  const response = await fetch(`${API_BASE}/api/uboats/routes`);
  if (!response.ok) {
    throw new Error(`Failed to fetch routes: ${response.status}`);
  }
  return response.json();
}

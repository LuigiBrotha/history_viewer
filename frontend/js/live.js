export function mergeRoutes(routes, changed) {
  const byId = new Map(changed.map((route) => [route.external_id, route]));
  const seen = new Set();
  const merged = routes.map((route) => {
    if (byId.has(route.external_id)) {
      seen.add(route.external_id);
      return byId.get(route.external_id);
    }
    return route;
  });
  for (const route of changed) {
    if (!seen.has(route.external_id)) {
      seen.add(route.external_id);
      merged.push(route);
    }
  }
  return merged;
}

export function uncomputedLegs(routes) {
  let count = 0;
  for (const route of routes) {
    for (const leg of route.legs ?? []) {
      if (leg.status === "not_computed") count += 1;
    }
  }
  return count;
}

// What still asks for attention: boats that failed and legs not yet computed. The crawl's
// progress and its last boat are left out (the user no longer needs them); "" when all is well.
export function statusLine(status, now, uncomputed = 0) {
  const parts = [];
  if (status.boats_failed > 0) parts.push(`${status.boats_failed} mislukt`);
  if (uncomputed > 0) {
    parts.push(uncomputed === 1 ? "1 traject nog niet berekend" : `${uncomputed} trajecten nog niet berekend`);
  }
  return parts.join(" · ");
}

// Two writers can commit out of order, so a patrol can land just behind the revision
// that was already seen. Asking for a margin back is safe because mergeRoutes dedupes.
const CURSOR_MARGIN_MS = 5000;

function sinceCursor(revision) {
  if (revision == null) return null;
  return new Date(new Date(revision).getTime() - CURSOR_MARGIN_MS).toISOString();
}

// Ships are fetched apart from the routes: a new revision brings the ships that changed since
// the previous one. A failed fetch keeps the old revision, so the next call tries again.
export function createShipLoader({ fetchShips, onShips, onError }) {
  let loaded = false;
  let revision = null;
  let busy = false;

  return async function load(newRevision) {
    if (busy || (loaded && newRevision === revision)) return;
    busy = true;
    try {
      const changed = await fetchShips(loaded ? sinceCursor(revision) : null);
      loaded = true;
      revision = newRevision;
      onShips(changed);
    } catch (error) {
      onError(error);
    } finally {
      busy = false;
    }
  };
}

export function startPolling({
  intervalMs,
  fetchStatus,
  fetchRoutes,
  isHidden,
  onData,
  onStatus,
  onError,
  setTimer,
}) {
  let stopped = false;
  let loaded = false;
  let revision = null;

  // A rendering failure is a bug, not a lost connection: log it, keep polling.
  function guarded(handler, value) {
    try {
      handler(value);
    } catch (error) {
      console.error(error);
    }
  }

  async function poll() {
    if (stopped) return;
    if (!isHidden()) {
      try {
        const status = await fetchStatus();
        guarded(onStatus, status);
        if (!loaded || status.revision !== revision) {
          const changed = await fetchRoutes(sinceCursor(revision));
          // The fetch succeeded, so the cursor advances even if rendering it fails.
          loaded = true;
          revision = status.revision;
          guarded(onData, changed);
        }
      } catch (error) {
        onError(error);
      }
    }
    if (!stopped) setTimer(poll, intervalMs);
  }

  poll();
  return {
    stop() {
      stopped = true;
    },
  };
}

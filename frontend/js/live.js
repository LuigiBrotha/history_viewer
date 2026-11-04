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

function ageText(crawledAt, now) {
  const seconds = Math.max(0, Math.floor((now - new Date(crawledAt)) / 1000));
  if (seconds < 60) return `${seconds} sec geleden`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min geleden`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} uur geleden`;
  return `${Math.floor(hours / 24)} dagen geleden`;
}

export function statusLine(status, now) {
  const progress =
    status.listing_total == null
      ? `${status.boats_crawled} boten`
      : `${status.boats_crawled} van ${status.listing_total} boten`;
  let line = progress;
  if (status.last_patrol) {
    line += ` · laatste: ${status.last_patrol.boat_number}, ${ageText(status.last_patrol.crawled_at, now)}`;
  }
  if (status.boats_failed > 0) {
    line += ` · ${status.boats_failed} mislukt`;
  }
  return line;
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

  async function poll() {
    if (stopped) return;
    if (!isHidden()) {
      try {
        const status = await fetchStatus();
        onStatus(status);
        if (!loaded || status.revision !== revision) {
          const changed = await fetchRoutes(revision);
          onData(changed);
          loaded = true;
          revision = status.revision;
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

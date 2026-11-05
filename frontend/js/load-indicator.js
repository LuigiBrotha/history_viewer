import { fetchAllRoutes, fetchRoutes } from "./api.js";

const FAILED = "Laden mislukt, opnieuw proberen…";

// 100 is reserved for the moment the data is actually on the page.
export function loadPercent(received, total) {
  return total ? Math.min(99, Math.floor((received / total) * 100)) : 0;
}

export function loadDetail(received, total) {
  // A running crawl can add patrols after the total was read.
  return total ? `${Math.min(received, total)} van ${total} patrouilles` : "Verbinden…";
}

// A fetchRoutes for startPolling: the first full load goes page by page and fills the
// indicator, later updates are small and pass by without it. Call setTotal from onStatus,
// which startPolling calls before fetching, and finish after the data has been drawn.
export function createLoadIndicator(rootEl) {
  const percentEl = document.createElement("div");
  percentEl.className = "load-percent";
  const barEl = document.createElement("div");
  barEl.className = "load-bar";
  const fillEl = document.createElement("div");
  barEl.append(fillEl);
  const detailEl = document.createElement("div");
  rootEl.setAttribute("role", "progressbar");
  rootEl.setAttribute("aria-valuemin", "0");
  rootEl.setAttribute("aria-valuemax", "100");
  rootEl.setAttribute("aria-label", "Routes laden");
  rootEl.append(percentEl, barEl, detailEl);

  let total = null;
  let received = 0;

  function render() {
    const percent = loadPercent(received, total);
    percentEl.textContent = `${percent}%`;
    fillEl.style.width = `${percent}%`;
    detailEl.textContent = loadDetail(received, total);
    rootEl.setAttribute("aria-valuenow", String(percent));
  }
  render();

  return {
    setTotal(value) {
      total = value;
      render();
    },
    finish() {
      rootEl.hidden = true;
    },
    fetchRoutes: async (since) => {
      if (since) {
        return fetchRoutes(since);
      }
      try {
        return await fetchAllRoutes({
          onProgress: (count) => {
            received = count;
            render();
          },
        });
      } catch (error) {
        received = 0;
        render();
        detailEl.textContent = FAILED;
        throw error;
      }
    },
  };
}

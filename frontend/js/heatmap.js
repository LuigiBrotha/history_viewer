import { addBaseMaps } from "./base-maps.js";
import { fetchStatus } from "./api.js";
import { createLoadIndicator } from "./load-indicator.js";
import { initAtlas } from "./atlas.js";
import { initBattles } from "./battles.js";
import { isPacificShown } from "./pacific-view.js";
import { rampGradient } from "./color-ramp.js";
import { CELL_DEGREES, COLUMNS, densityGrid, heatColor, patrolCells, ROWS, scaleMax, smooth } from "./heat-model.js";
import { mergeRoutes, statusLine, startPolling, uncomputedLegs } from "./live.js";
import { initPeriodSlider } from "./period-slider.js";
import { historyRange } from "./status-map.js";

const POLL_INTERVAL_MS = 5000;
const NO_CONNECTION = "Geen verbinding, opnieuw proberen…";
const MAP_FAILED = "Kaart kon niet laden";
const NORTH = 84;
const SOUTH = -75;
const PANE = "heat";
// Above the historical map, below the map controls.
const PANE_Z_INDEX = 380;

function mercatorY(lat) {
  return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
}

// The grid is even in degrees; Leaflet stretches an overlay evenly in Web Mercator.
function rowLookup(height) {
  const top = mercatorY(NORTH);
  const bottom = mercatorY(SOUTH);
  return Array.from({ length: height }, (_, y) => {
    const my = top - ((y + 0.5) / height) * (top - bottom);
    const lat = ((2 * Math.atan(Math.exp(my)) - Math.PI / 2) * 180) / Math.PI;
    return Math.min(ROWS - 1, Math.max(0, Math.floor((lat + 90) / CELL_DEGREES)));
  });
}

function main() {
  const liveStatusEl = document.getElementById("live-status");
  if (typeof L === "undefined") {
    liveStatusEl.textContent = MAP_FAILED;
    return;
  }

  const map = L.map("status-map").setView([54.5, 8.0], 3);
  addBaseMaps(map);
  map.createPane(PANE);
  map.getPane(PANE).style.zIndex = PANE_Z_INDEX;
  map.getPane(PANE).style.pointerEvents = "none";

  const height = Math.round((COLUMNS * (mercatorY(NORTH) - mercatorY(SOUTH))) / (2 * Math.PI));
  const rows = rowLookup(height);
  const canvas = document.createElement("canvas");
  canvas.width = COLUMNS;
  canvas.height = height;
  const context = canvas.getContext("2d");
  const overlay = L.imageOverlay(canvas.toDataURL(), [[SOUTH, -180], [NORTH, 180]], { pane: PANE, interactive: false }).addTo(map);

  const countEl = document.getElementById("route-count");
  const maxEl = document.getElementById("heat-max");
  document.getElementById("heat-ramp").style.background = rampGradient();

  const entries = new Map();
  let routes = [];
  let lastStatus = null;
  let history = null;
  let period = { from: null, to: null };
  let fitted = false;
  let atlas = { setDate() {} };

  function renderStatusLine() {
    if (lastStatus !== null) {
      liveStatusEl.textContent = statusLine(lastStatus, new Date(), uncomputedLegs(routes));
    }
  }

  function renderAtlas() {
    const end = period.to ?? history?.max ?? null;
    if (end !== null) {
      atlas.setDate(end);
    }
  }

  function renderHeat() {
    const { grid, patrols } = densityGrid(entries.values(), period.from, period.to);
    const smoothed = smooth(grid);
    const max = scaleMax(smoothed);
    const rawMax = grid.reduce((highest, value) => Math.max(highest, value), 0);

    const image = context.createImageData(COLUMNS, height);
    for (let y = 0; y < height; y++) {
      const rowStart = rows[y] * COLUMNS;
      for (let x = 0; x < COLUMNS; x++) {
        const value = smoothed[rowStart + x];
        if (value > 0) {
          image.data.set(heatColor(value, max), (y * COLUMNS + x) * 4);
        }
      }
    }
    context.putImageData(image, 0, 0);
    overlay.setUrl(canvas.toDataURL());

    countEl.textContent = `${patrols} van ${entries.size} patrouilles`;
    maxEl.textContent = `Drukste gebied: ${rawMax} ${rawMax === 1 ? "patrouille" : "patrouilles"}`;
  }

  const windowEl = document.getElementById("slider-window");
  const slider = initPeriodSlider({
    trackEl: document.getElementById("slider-track"),
    windowEl,
    fromHandleEl: document.getElementById("slider-from"),
    toHandleEl: document.getElementById("slider-to"),
    ticksEl: document.getElementById("slider-ticks"),
    labelEl: document.getElementById("period-label"),
    resetEl: document.getElementById("period-reset"),
    onChange: (next) => {
      period = next;
      battles.setPeriod(next.from, next.to);
      renderHeat();
      renderAtlas();
    },
  });

  const battles = initBattles({ map, mode: "period" });
  battles.setPeriod(null, null);

  initAtlas(map).then((loaded) => {
    atlas = loaded;
    renderAtlas();
  });

  const loadIndicator = createLoadIndicator(document.getElementById("load-indicator"));

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes: loadIndicator.fetchRoutes,
    isHidden: () => document.hidden,
    onData: (changed) => {
      try {
        routes = mergeRoutes(routes, changed);
        for (const patrol of changed) {
          entries.set(patrol.external_id, { patrol, cells: patrolCells(patrol) });
        }
        history = historyRange(routes);
        if (history !== null) {
          slider.setBounds(history);
        }
        renderStatusLine();
        renderHeat();
        renderAtlas();
        const points = routes.flatMap((patrol) => patrol.points.map((point) => [point.lat, point.lng]));
        if (!fitted && points.length > 0) {
          fitted = true;
          if (!isPacificShown(map)) {
            map.fitBounds(points, { padding: [40, 40] });
          }
        }
      } finally {
        loadIndicator.finish();
      }
    },
    onStatus: (status) => {
      loadIndicator.setTotal(status.patrol_count);
      lastStatus = status;
      renderStatusLine();
    },
    onError: (error) => {
      console.error(error);
      liveStatusEl.textContent = NO_CONNECTION;
    },
    setTimer: (fn, ms) => setTimeout(fn, ms),
  });
}

main();

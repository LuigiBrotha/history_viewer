import { fetchShips, fetchStatus } from "./api.js";
import { createShipLoader, startPolling, statusLine } from "./live.js";
import { mergeShips } from "./ship-model.js";
import {
  boatSeries,
  colorSlots,
  formatNumber,
  formatTons,
  matchSeries,
  niceMax,
  periodLabel,
  segmentAt,
  stackedBars,
  tableRows,
} from "./tonnage-model.js";

const POLL_INTERVAL_MS = 5000;
const NO_CONNECTION = "Geen verbinding, opnieuw proberen…";
const SLOT_COUNT = 8;
const MAX_TOOLTIP_SHIPS = 4;
const DIMMED_ALPHA = 0.35;
const MARGIN = { top: 12, right: 16, bottom: 26, left: 72 };
const Y_TICKS = 5;
const MIN_YEAR_LABEL_GAP = 40;

function main() {
  const canvas = document.getElementById("tonnage-chart");
  const context = canvas.getContext("2d");
  const tooltipEl = document.getElementById("tonnage-tooltip");
  const legendEl = document.getElementById("tonnage-legend");
  const bodyEl = document.getElementById("tonnage-rows");
  const countEl = document.getElementById("tonnage-count");
  const searchEl = document.getElementById("tonnage-search");
  const unitEl = document.getElementById("tonnage-unit");
  const liveStatusEl = document.getElementById("live-status");
  const rootStyle = getComputedStyle(document.querySelector(".tonnage-page"));

  let ships = [];
  let series = [];
  let selected = null;
  let hovered = null;
  let bars = [];
  let unit = "month";
  const slots = new Map();
  let scale = null;

  function color(name) {
    return rootStyle.getPropertyValue(name).trim();
  }

  function slotColor(slug) {
    return slots.has(slug) ? color(`--series-${slots.get(slug) + 1}`) : null;
  }

  function buildScale(width, height) {
    if (bars.length === 0) {
      return null;
    }
    const top = niceMax(bars[bars.length - 1].total);
    const plotWidth = Math.max(10, width - MARGIN.left - MARGIN.right);
    const plotHeight = Math.max(10, height - MARGIN.top - MARGIN.bottom);
    const step = plotWidth / bars.length;
    return {
      top,
      step,
      barWidth: Math.max(1, step >= 4 ? step - 1 : step),
      x: (index) => MARGIN.left + index * step,
      y: (tons) => MARGIN.top + plotHeight - (tons / top) * plotHeight,
      tonsAt: (y) => ((MARGIN.top + plotHeight - y) / plotHeight) * top,
      plotWidth,
      plotHeight,
    };
  }

  function drawSegment(index, segment, fill) {
    const y = scale.y(segment.to);
    const height = scale.y(segment.from) - y;
    context.fillStyle = fill;
    // A sliver of surface keeps boats apart wherever a block is tall enough to spare it.
    context.fillRect(scale.x(index), y, scale.barWidth, height >= 3 ? height - 1 : Math.max(height, 0.5));
  }

  function drawYearLabels() {
    const years = [];
    bars.forEach((bar, index) => {
      const year = bar.period.slice(0, 4);
      if (years.length === 0 || years[years.length - 1].year !== year) {
        years.push({ year, x: scale.x(index) });
      }
    });
    context.textAlign = "left";
    context.textBaseline = "top";
    context.fillStyle = color("--text-secondary");
    years.forEach(({ year, x }, index) => {
      const next = years[index + 1];
      if (next === undefined || next.x - x >= MIN_YEAR_LABEL_GAP) {
        context.fillText(year, x, MARGIN.top + scale.plotHeight + 8);
      }
    });
  }

  function draw() {
    const box = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(box.width * ratio);
    canvas.height = Math.round(box.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, box.width, box.height);
    scale = buildScale(box.width, box.height);
    if (scale === null) {
      context.fillStyle = color("--text-secondary");
      context.font = "14px system-ui, sans-serif";
      context.fillText("Nog geen gezonken schepen binnengehaald.", MARGIN.left, 40);
      return;
    }

    context.font = "12px system-ui, sans-serif";
    context.lineWidth = 1;
    context.textBaseline = "middle";
    for (let i = 0; i <= Y_TICKS; i++) {
      const tons = (scale.top / Y_TICKS) * i;
      const y = Math.round(scale.y(tons)) + 0.5;
      context.strokeStyle = color("--grid");
      context.beginPath();
      context.moveTo(MARGIN.left, y);
      context.lineTo(MARGIN.left + scale.plotWidth, y);
      context.stroke();
      context.fillStyle = color("--text-secondary");
      context.textAlign = "right";
      context.fillText(formatNumber(Math.round(tons)), MARGIN.left - 8, y);
    }
    drawYearLabels();

    const contextFill = color("--context");
    const slotFills = new Map([...slots].map(([slug, slot]) => [slug, color(`--series-${slot + 1}`)]));
    const focus = selected?.slug ?? hovered ?? null;
    const focusFill = slotFills.get(focus) ?? color("--text-primary");
    bars.forEach((bar, index) => {
      context.globalAlpha = focus === null ? 1 : DIMMED_ALPHA;
      for (const segment of bar.segments) {
        if (segment.slug !== focus) {
          drawSegment(index, segment, slotFills.get(segment.slug) ?? contextFill);
        }
      }
      context.globalAlpha = 1;
      const focused = bar.segments.find((segment) => segment.slug === focus);
      if (focused !== undefined) {
        drawSegment(index, focused, focusFill);
      }
    });
  }

  function showTooltip(bar, segment, x, y) {
    tooltipEl.replaceChildren();
    const line = (content) => {
      const row = document.createElement("div");
      row.textContent = content;
      tooltipEl.append(row);
    };
    const title = document.createElement("strong");
    title.textContent = segment === null ? "Alle boten" : segment.number;
    tooltipEl.append(title);
    line(periodLabel(bar.period, unit));
    if (segment !== null) {
      line(`Tot en met deze periode: ${formatTons(segment.to - segment.from)}`);
      if (segment.ships.length > 0) {
        line(`In deze periode: ${formatTons(segment.added)}`);
        const shown = segment.ships.slice(0, MAX_TOOLTIP_SHIPS).join(", ");
        const others = segment.ships.length - MAX_TOOLTIP_SHIPS;
        line(others > 0 ? `${shown} en ${others} andere` : shown);
      }
    }
    line(`Alle boten samen: ${formatTons(bar.total)}`);
    tooltipEl.hidden = false;
    const box = canvas.getBoundingClientRect();
    const left = Math.min(x + 12, box.width - tooltipEl.offsetWidth - 4);
    tooltipEl.style.left = `${Math.max(4, left)}px`;
    tooltipEl.style.top = `${Math.max(4, y - tooltipEl.offsetHeight - 8)}px`;
  }

  function hide() {
    hovered = null;
    tooltipEl.hidden = true;
    draw();
  }

  function pointerAt(event) {
    if (scale === null) {
      return null;
    }
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    const bar = bars[Math.floor((x - MARGIN.left) / scale.step)];
    if (bar === undefined) {
      return null;
    }
    return { x, y, bar, segment: segmentAt(bar, scale.tonsAt(y)) };
  }

  function showAt(event) {
    const at = pointerAt(event);
    if (at === null) {
      hide();
      return;
    }
    const next = at.segment?.slug ?? null;
    if (next !== hovered) {
      hovered = next;
      draw();
    }
    showTooltip(at.bar, at.segment, at.x, at.y);
  }

  canvas.addEventListener("pointermove", showAt);
  canvas.addEventListener("pointerdown", showAt);
  // A finger lifting is not leaving: the tooltip stays until the next tap.
  canvas.addEventListener("pointerleave", (event) => {
    if (event.pointerType !== "touch") {
      hide();
    }
  });
  canvas.addEventListener("click", (event) => {
    const at = pointerAt(event);
    if (at !== null && at.segment !== null) {
      const line = series.find((candidate) => candidate.slug === at.segment.slug);
      select(selected?.slug === line.slug ? null : line);
    }
  });

  for (const button of unitEl.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      unit = button.dataset.unit;
      for (const other of unitEl.querySelectorAll("button")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      bars = stackedBars(series, unit);
      tooltipEl.hidden = true;
      draw();
    });
  }

  function select(line) {
    selected = line;
    for (const row of bodyEl.children) {
      row.classList.toggle("selected", row.dataset.slug === line?.slug);
    }
    draw();
  }

  searchEl.addEventListener("input", () => {
    select(matchSeries(series, searchEl.value));
  });

  function renderLegend() {
    legendEl.replaceChildren();
    for (const line of series) {
      if (slots.has(line.slug)) {
        const item = document.createElement("button");
        item.type = "button";
        const swatch = document.createElement("span");
        swatch.className = "tonnage-swatch";
        swatch.style.background = slotColor(line.slug);
        item.append(swatch, line.number);
        item.addEventListener("click", () => select(selected?.slug === line.slug ? null : line));
        legendEl.append(item);
      }
    }
    if (series.length > slots.size) {
      const others = document.createElement("span");
      others.className = "tonnage-others";
      const swatch = document.createElement("span");
      swatch.className = "tonnage-swatch";
      swatch.style.background = color("--context");
      others.append(swatch, "Overige boten");
      legendEl.append(others);
    }
  }

  function renderTable() {
    bodyEl.replaceChildren();
    for (const row of tableRows(series)) {
      const tr = document.createElement("tr");
      tr.dataset.slug = row.slug;
      tr.tabIndex = 0;
      if (row.slug === selected?.slug) {
        tr.classList.add("selected");
      }
      for (const value of [row.boat, row.tons, row.ships]) {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      }
      const choose = () => {
        const line = series.find((candidate) => candidate.slug === row.slug);
        select(selected?.slug === row.slug ? null : line);
      };
      tr.addEventListener("click", choose);
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          choose();
        }
      });
      bodyEl.append(tr);
    }
  }

  const loadShips = createShipLoader({
    fetchShips,
    onShips: (changed) => {
      ships = mergeShips(ships, changed);
      series = boatSeries(ships);
      bars = stackedBars(series, unit);
      colorSlots(series, slots, SLOT_COUNT);
      if (selected !== null) {
        selected = series.find((line) => line.slug === selected.slug) ?? null;
      }
      countEl.textContent = `${series.length} ${series.length === 1 ? "boot" : "boten"}`;
      renderLegend();
      renderTable();
      draw();
    },
    onError: (error) => console.error(error),
  });

  window.addEventListener("resize", draw);

  startPolling({
    intervalMs: POLL_INTERVAL_MS,
    fetchStatus,
    fetchRoutes: async () => [],
    isHidden: () => document.hidden,
    onData: () => {},
    onStatus: (status) => {
      liveStatusEl.textContent = statusLine(status, new Date());
      loadShips(status.revision);
    },
    onError: (error) => {
      console.error(error);
      liveStatusEl.textContent = NO_CONNECTION;
    },
    setTimer: (fn, ms) => setTimeout(fn, ms),
  });
  draw();
}

main();

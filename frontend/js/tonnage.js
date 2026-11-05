import { fetchShips, fetchStatus } from "./api.js";
import { createShipLoader, startPolling, statusLine } from "./live.js";
import { mergeShips } from "./ship-model.js";
import {
  boatSeries,
  colorSlots,
  formatTons,
  matchSeries,
  nearestSeries,
  niceMax,
  tableRows,
  tonsOn,
} from "./tonnage-model.js";

const POLL_INTERVAL_MS = 5000;
const NO_CONNECTION = "Geen verbinding, opnieuw proberen…";
const SLOT_COUNT = 8;
const MARGIN = { top: 12, right: 16, bottom: 26, left: 72 };
const Y_TICKS = 5;
const DAY_MS = 24 * 60 * 60 * 1000;

function main() {
  const canvas = document.getElementById("tonnage-chart");
  const context = canvas.getContext("2d");
  const tooltipEl = document.getElementById("tonnage-tooltip");
  const legendEl = document.getElementById("tonnage-legend");
  const bodyEl = document.getElementById("tonnage-rows");
  const countEl = document.getElementById("tonnage-count");
  const searchEl = document.getElementById("tonnage-search");
  const liveStatusEl = document.getElementById("live-status");
  const rootStyle = getComputedStyle(document.querySelector(".tonnage-page"));

  let ships = [];
  let series = [];
  let selected = null;
  let hovered = null;
  let crosshairX = null;
  const slots = new Map();
  let scale = null;

  function color(name) {
    return rootStyle.getPropertyValue(name).trim();
  }

  function slotColor(slug) {
    return slots.has(slug) ? color(`--series-${slots.get(slug) + 1}`) : null;
  }

  function buildScale(width, height) {
    if (series.length === 0) {
      return null;
    }
    const dates = series.flatMap(({ steps }) => [steps[0].date, steps[steps.length - 1].date]).sort();
    const min = Date.parse(`${dates[0].slice(0, 4)}-01-01`);
    const max = Date.parse(dates[dates.length - 1]) + 30 * DAY_MS;
    const top = niceMax(series[0].total);
    const plotWidth = Math.max(10, width - MARGIN.left - MARGIN.right);
    const plotHeight = Math.max(10, height - MARGIN.top - MARGIN.bottom);
    return {
      min,
      max,
      top,
      x: (date) => MARGIN.left + ((Date.parse(date) - min) / (max - min)) * plotWidth,
      y: (tons) => MARGIN.top + plotHeight - (tons / top) * plotHeight,
      dateAt: (x) => new Date(min + ((x - MARGIN.left) / plotWidth) * (max - min)).toISOString().slice(0, 10),
      tonsAt: (y) => ((MARGIN.top + plotHeight - y) / plotHeight) * top,
      plotWidth,
      plotHeight,
    };
  }

  function drawLine(line, stroke, width) {
    const { x, y } = scale;
    context.beginPath();
    context.moveTo(x(line.steps[0].date), y(0));
    let previous = 0;
    for (const step of line.steps) {
      context.lineTo(x(step.date), y(previous));
      context.lineTo(x(step.date), y(step.total));
      previous = step.total;
    }
    context.lineTo(MARGIN.left + scale.plotWidth, y(previous));
    context.strokeStyle = stroke;
    context.lineWidth = width;
    context.stroke();
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
      context.fillText(Math.round(tons).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "."), MARGIN.left - 8, y);
    }
    context.textAlign = "center";
    context.textBaseline = "top";
    const firstYear = new Date(scale.min).getUTCFullYear();
    const lastYear = new Date(scale.max).getUTCFullYear();
    for (let year = firstYear; year <= lastYear; year++) {
      const x = scale.x(`${year}-01-01`);
      if (x >= MARGIN.left && x <= MARGIN.left + scale.plotWidth) {
        context.fillStyle = color("--text-secondary");
        context.fillText(String(year), x, MARGIN.top + scale.plotHeight + 8);
      }
    }

    for (const line of series) {
      if (!slots.has(line.slug)) {
        drawLine(line, color("--context"), 1);
      }
    }
    for (const line of series) {
      if (slots.has(line.slug)) {
        drawLine(line, slotColor(line.slug), 2);
      }
    }
    const focus = selected ?? hovered;
    if (focus !== null) {
      drawLine(focus, color("--surface"), 5);
      drawLine(focus, slotColor(focus.slug) ?? color("--text-primary"), 2.5);
      const last = focus.steps[focus.steps.length - 1];
      context.fillStyle = color("--text-primary");
      context.font = "600 13px system-ui, sans-serif";
      context.textAlign = "right";
      context.textBaseline = "bottom";
      context.fillText(focus.number, MARGIN.left + scale.plotWidth, scale.y(last.total) - 4);
    }
    if (crosshairX !== null) {
      context.strokeStyle = color("--text-secondary");
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(crosshairX + 0.5, MARGIN.top);
      context.lineTo(crosshairX + 0.5, MARGIN.top + scale.plotHeight);
      context.stroke();
    }
  }

  function showTooltip(line, date, x, y) {
    tooltipEl.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = line.number;
    const total = document.createElement("div");
    total.textContent = `${date}: ${formatTons(tonsOn(line, date))}`;
    tooltipEl.append(title, total);
    const lastStep = [...line.steps].reverse().find((step) => step.date <= date);
    if (lastStep) {
      const last = document.createElement("div");
      last.textContent = `Laatste schip: ${lastStep.name} (${lastStep.date})`;
      tooltipEl.append(last);
    }
    tooltipEl.hidden = false;
    const box = canvas.getBoundingClientRect();
    const left = Math.min(x + 12, box.width - tooltipEl.offsetWidth - 4);
    tooltipEl.style.left = `${Math.max(4, left)}px`;
    tooltipEl.style.top = `${Math.max(4, y - tooltipEl.offsetHeight - 8)}px`;
  }

  function hide() {
    hovered = null;
    crosshairX = null;
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
    if (x < MARGIN.left || x > MARGIN.left + scale.plotWidth) {
      return null;
    }
    const date = scale.dateAt(x);
    return { x, y, date, line: nearestSeries(series, date, scale.tonsAt(y)) };
  }

  canvas.addEventListener("pointermove", (event) => {
    const at = pointerAt(event);
    if (at === null || at.line === null) {
      hide();
      return;
    }
    hovered = at.line;
    crosshairX = at.x;
    draw();
    showTooltip(selected ?? at.line, at.date, at.x, at.y);
  });
  canvas.addEventListener("pointerleave", hide);
  canvas.addEventListener("click", (event) => {
    const at = pointerAt(event);
    if (at !== null && at.line !== null) {
      select(selected?.slug === at.line.slug ? null : at.line);
    }
  });

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

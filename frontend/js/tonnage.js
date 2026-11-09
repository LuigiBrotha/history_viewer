import { fetchPatrolPeriods, fetchShips, fetchStatus } from "./api.js";
import { createShipLoader, startPolling, statusLine } from "./live.js";
import { mergeShips } from "./ship-model.js";
import {
  barPosition,
  barsFor,
  boatSeries,
  colorSlots,
  dotAt,
  formatNumber,
  formatTons,
  happyTimeOf,
  happyTimeSpans,
  matchSeries,
  niceMax,
  outcomeLabel,
  periodLabel,
  segmentAt,
  shipDots,
  tableRows,
} from "./tonnage-model.js";
import { createShipArticle } from "./tonnage-article.js";

const POLL_INTERVAL_MS = 5000;
const NO_CONNECTION = "Geen verbinding, opnieuw proberen…";
const SLOT_COUNT = 8;
const MAX_TOOLTIP_SHIPS = 4;
const DIMMED_ALPHA = 0.35;
// The top margin holds the names of the Happy Times, above the tallest bars.
const MARGIN = { top: 30, right: 16, bottom: 26, left: 72 };
const BAND_LABEL_OFFSET = 22;
const VIEWS = {
  periode: {
    title: "Gezonken tonnage per periode, per U-boot",
    note: "Wat er in elke periode zonk. Beide Happy Times steken boven de maanden ervoor uit.",
  },
  rendement: {
    title: "Gezonken tonnage per U-boot per dag op zee",
    note: "Gezonken tonnage gedeeld door het aantal dagen dat de boten op zee waren. Hier springt de First Happy Time eruit: met weinig boten werd het meest gezonken per boot.",
  },
  amerika: {
    title: "Gezonken tonnage in Amerikaanse wateren",
    note: "Alleen schepen ten westen van 50° W en ten zuiden van 52° N: de Amerikaanse kust, de Golf en de Caribische Zee. Hier zie je de Second Happy Time beginnen, in januari 1942.",
  },
  cumulatief: {
    title: "Gezonken tonnage, cumulatief per U-boot",
    note: "Het totaal tot en met elke periode. Een Happy Time is hier alleen een steiler stuk.",
  },
};
const Y_TICKS = 5;
const DOT_RADIUS = 2.5;
const FOCUS_DOT_RADIUS = 3.5;
const DOT_REACH = 8;
const DOT_ALPHA = 0.6;
const DIMMED_DOT_ALPHA = 0.15;
const MIN_YEAR_LABEL_GAP = 40;

function main() {
  const canvas = document.getElementById("tonnage-chart");
  const context = canvas.getContext("2d");
  const dotsCanvas = document.getElementById("tonnage-dots");
  const dotsContext = dotsCanvas.getContext("2d");
  const dotsTooltipEl = document.getElementById("tonnage-dots-tooltip");
  const tooltipEl = document.getElementById("tonnage-tooltip");
  const legendEl = document.getElementById("tonnage-legend");
  const bodyEl = document.getElementById("tonnage-rows");
  const countEl = document.getElementById("tonnage-count");
  const searchEl = document.getElementById("tonnage-search");
  const unitEl = document.getElementById("tonnage-unit");
  const viewEl = document.getElementById("tonnage-view");
  const titleEl = document.getElementById("tonnage-title");
  const viewNoteEl = document.getElementById("tonnage-view-note");
  const liveStatusEl = document.getElementById("live-status");
  const rootStyle = getComputedStyle(document.querySelector(".tonnage-page"));

  let ships = [];
  let series = [];
  let selected = null;
  let hovered = null;
  let bars = [];
  let unit = "month";
  let view = "periode";
  let patrolPeriods = [];
  let periodsRevision = null;
  const slots = new Map();
  let scale = null;
  let dots = [];
  let hoveredDot = null;
  // The charts take the width the panel leaves them, so they are drawn again when it comes or goes.
  const shipArticle = createShipArticle({
    rootEl: document.getElementById("article-pane"),
    getShips: () => ships,
    onToggle: () => draw(),
  });

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
    const top = niceMax(Math.max(...bars.map((bar) => bar.total)));
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

  function drawHappyTimes(ctx, plotHeight) {
    ctx.font = "600 12px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const { name, short, first, last } of happyTimeSpans(bars, unit)) {
      const x = scale.x(first);
      const width = (last - first + 1) * scale.step;
      const top = MARGIN.top - BAND_LABEL_OFFSET;
      ctx.fillStyle = color("--happy-band");
      ctx.fillRect(x, top, width, MARGIN.top + plotHeight - top);
      ctx.fillStyle = color("--happy-text");
      const text = ctx.measureText(name).width <= width ? name : short;
      ctx.fillText(text, x + width / 2, top + 4);
    }
    ctx.font = "12px system-ui, sans-serif";
  }

  function drawYearLabels(ctx, plotHeight) {
    const years = [];
    bars.forEach((bar, index) => {
      const year = bar.period.slice(0, 4);
      if (years.length === 0 || years[years.length - 1].year !== year) {
        years.push({ year, x: scale.x(index) });
      }
    });
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillStyle = color("--text-secondary");
    years.forEach(({ year, x }, index) => {
      const next = years[index + 1];
      if (next === undefined || next.x - x >= MIN_YEAR_LABEL_GAP) {
        ctx.fillText(year, x, MARGIN.top + plotHeight + 8);
      }
    });
  }

  function drawGrid(ctx, top, y) {
    ctx.font = "12px system-ui, sans-serif";
    ctx.lineWidth = 1;
    ctx.textBaseline = "middle";
    for (let i = 0; i <= Y_TICKS; i++) {
      const tons = (top / Y_TICKS) * i;
      const lineY = Math.round(y(tons)) + 0.5;
      ctx.strokeStyle = color("--grid");
      ctx.beginPath();
      ctx.moveTo(MARGIN.left, lineY);
      ctx.lineTo(MARGIN.left + scale.plotWidth, lineY);
      ctx.stroke();
      ctx.fillStyle = color("--text-secondary");
      ctx.textAlign = "right";
      ctx.fillText(formatNumber(Math.round(tons)), MARGIN.left - 8, lineY);
    }
  }

  // Sunk and captured ships are filled, damaged ones hollow, as on the map.
  function paintDot(dot, radius, paint) {
    dotsContext.beginPath();
    dotsContext.arc(dot.x, dot.y, radius, 0, 2 * Math.PI);
    dotsContext.fillStyle = paint;
    dotsContext.strokeStyle = paint;
    if (dot.ship.outcome === "damaged") {
      dotsContext.stroke();
    } else {
      dotsContext.fill();
    }
  }

  // Every ship as a dot under the bars: the same date axis, its own axis of tons.
  function drawDots() {
    const box = dotsCanvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    dotsCanvas.width = Math.round(box.width * ratio);
    dotsCanvas.height = Math.round(box.height * ratio);
    dotsContext.setTransform(ratio, 0, 0, ratio, 0, 0);
    dotsContext.clearRect(0, 0, box.width, box.height);
    dots = [];
    const shown = shipDots(ships, view);
    if (scale === null || shown.length === 0) {
      return;
    }
    const top = niceMax(Math.max(...shown.map((ship) => ship.tons)));
    const plotHeight = Math.max(10, box.height - MARGIN.top - MARGIN.bottom);
    const y = (tons) => MARGIN.top + plotHeight - (tons / top) * plotHeight;
    drawGrid(dotsContext, top, y);
    drawHappyTimes(dotsContext, plotHeight);
    drawYearLabels(dotsContext, plotHeight);
    dots = shown.map((ship) => ({ ship, x: MARGIN.left + barPosition(ship.date, bars, unit) * scale.step, y: y(ship.tons) }));

    const focus = selected?.slug ?? hovered ?? null;
    const plain = color("--text-secondary");
    const lit = slotColor(focus) ?? color("--text-primary");
    dotsContext.lineWidth = 1.2;
    dotsContext.globalAlpha = focus === null ? DOT_ALPHA : DIMMED_DOT_ALPHA;
    for (const dot of dots) {
      if (dot.ship.boat_slug !== focus) {
        paintDot(dot, DOT_RADIUS, plain);
      }
    }
    dotsContext.globalAlpha = 1;
    for (const dot of dots) {
      if (dot.ship.boat_slug === focus) {
        paintDot(dot, FOCUS_DOT_RADIUS, lit);
      }
    }
    for (const ship of [shipArticle.current(), hoveredDot]) {
      const active = dots.find((dot) => dot.ship === ship);
      if (active !== undefined) {
        paintDot(active, FOCUS_DOT_RADIUS + 1.5, color("--text-primary"));
      }
    }
  }

  function showDotTooltip(dot) {
    dotsTooltipEl.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = dot.ship.name;
    dotsTooltipEl.append(title);
    const lines = [
      dot.ship.boat_number,
      periodLabel(dot.ship.date, "day"),
      formatTons(dot.ship.tons),
      outcomeLabel(dot.ship.outcome),
      "Klik voor het Artikel",
    ];
    for (const content of lines) {
      const row = document.createElement("div");
      row.textContent = content;
      dotsTooltipEl.append(row);
    }
    dotsTooltipEl.hidden = false;
    const box = dotsCanvas.getBoundingClientRect();
    const left = Math.min(dot.x + 12, box.width - dotsTooltipEl.offsetWidth - 4);
    dotsTooltipEl.style.left = `${Math.max(4, left)}px`;
    dotsTooltipEl.style.top = `${Math.max(4, dot.y - dotsTooltipEl.offsetHeight - 8)}px`;
  }

  function showDotAt(event) {
    const box = dotsCanvas.getBoundingClientRect();
    const dot = dotAt(dots, event.clientX - box.left, event.clientY - box.top, DOT_REACH);
    const next = dot?.ship ?? null;
    dotsCanvas.style.cursor = next === null ? "" : "pointer";
    if (next !== hoveredDot) {
      hoveredDot = next;
      drawDots();
    }
    if (dot === null) {
      dotsTooltipEl.hidden = true;
    } else {
      showDotTooltip(dot);
    }
  }

  dotsCanvas.addEventListener("click", (event) => {
    const box = dotsCanvas.getBoundingClientRect();
    const dot = dotAt(dots, event.clientX - box.left, event.clientY - box.top, DOT_REACH);
    if (dot !== null) {
      shipArticle.open(dot.ship);
      drawDots();
    }
  });
  dotsCanvas.addEventListener("pointermove", showDotAt);
  dotsCanvas.addEventListener("pointerdown", showDotAt);
  dotsCanvas.addEventListener("pointerleave", (event) => {
    if (event.pointerType !== "touch") {
      hoveredDot = null;
      dotsTooltipEl.hidden = true;
      drawDots();
    }
  });

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
      drawDots();
      return;
    }

    drawGrid(context, scale.top, scale.y);
    drawHappyTimes(context, scale.plotHeight);
    drawYearLabels(context, scale.plotHeight);

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
    drawDots();
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
    const happyTime = happyTimeOf(bar.period, unit);
    if (happyTime !== null) {
      line(happyTime.name);
    }
    if (segment !== null) {
      if (view === "cumulatief") {
        line(`Tot en met deze periode: ${formatTons(segment.to - segment.from)}`);
      }
      if (segment.ships.length > 0) {
        line(`In deze periode: ${formatTons(segment.added)}`);
        const shown = segment.ships.slice(0, MAX_TOOLTIP_SHIPS).join(", ");
        const others = segment.ships.length - MAX_TOOLTIP_SHIPS;
        line(others > 0 ? `${shown} en ${others} andere` : shown);
      }
    }
    if (view === "rendement") {
      line(`Alle boten: ${formatNumber(Math.round(bar.total))} ton per boot per dag op zee`);
      line(`${formatNumber(bar.boatDays)} bootdagen op zee`);
    } else {
      line(`Alle boten samen: ${formatTons(bar.total)}`);
    }
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

  function redraw() {
    bars = barsFor(view, { ships, series, periods: patrolPeriods, unit });
    tooltipEl.hidden = true;
    dotsTooltipEl.hidden = true;
    draw();
  }

  function pressOnly(groupEl, button) {
    for (const other of groupEl.querySelectorAll("button")) {
      other.setAttribute("aria-pressed", String(other === button));
    }
  }

  for (const button of unitEl.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      unit = button.dataset.unit;
      pressOnly(unitEl, button);
      redraw();
    });
  }

  function showViewText() {
    titleEl.textContent = VIEWS[view].title;
    viewNoteEl.textContent = VIEWS[view].note;
  }

  for (const button of viewEl.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      view = button.dataset.view;
      pressOnly(viewEl, button);
      showViewText();
      redraw();
    });
  }
  showViewText();

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
      bars = barsFor(view, { ships, series, periods: patrolPeriods, unit });
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

  async function loadPatrolPeriods(revision) {
    if (revision === periodsRevision) {
      return;
    }
    periodsRevision = revision;
    try {
      patrolPeriods = await fetchPatrolPeriods();
      redraw();
    } catch (error) {
      periodsRevision = null;
      console.error(error);
    }
  }

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
      loadPatrolPeriods(status.revision);
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

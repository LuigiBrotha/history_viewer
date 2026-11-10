// /histogram: how long Veldslagen last, each bar split by Benaming. Hover a bar for its counts,
// click a block for the Veldslagen in it, each linked to the map.
import { durationText } from "./battle-model.js";
import { MARGIN, hitTest, layout } from "./histogram-chart.js";
import { BENAMINGEN, histogram, isRough } from "./histogram-model.js";
import { writeView } from "./url-state.js";

const BATTLES_URL = "battles/battles.json";
const GAP = 2;
const RADIUS = 4;
const TICKS = 4;
const HATCH = 6;

const canvas = document.getElementById("histogram-chart");
const context = canvas.getContext("2d");
const tooltipEl = document.getElementById("histogram-tooltip");
const listEl = document.getElementById("histogram-list");
const rootStyle = getComputedStyle(document.querySelector(".histogram-page"));
const number = new Intl.NumberFormat("nl-NL");

let bars = [];
let geometry = null;
let size = { width: 0, height: 0 };
let hovered = null;
let chosen = null;

const color = (name) => rootStyle.getPropertyValue(name).trim();
// Each Benaming takes the next colour of the palette; a translated title has none (grey).
const fillOf = (key) => (key === "vertaald" ? color("--context") : color(`--series-${BENAMINGEN.findIndex((b) => b.key === key) + 1}`));

// Stripes of the block's colour over the surface: the rough part, known only by month or year.
const hatches = new Map();
function hatchOf(fill) {
  if (!hatches.has(fill)) {
    const tile = document.createElement("canvas");
    tile.width = HATCH;
    tile.height = HATCH;
    const ctx = tile.getContext("2d");
    ctx.fillStyle = color("--surface");
    ctx.fillRect(0, 0, HATCH, HATCH);
    ctx.strokeStyle = fill;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-1, HATCH + 1);
    ctx.lineTo(HATCH + 1, -1);
    ctx.moveTo(-1, 1);
    ctx.lineTo(1, -1);
    ctx.moveTo(HATCH - 1, HATCH + 1);
    ctx.lineTo(HATCH + 1, HATCH - 1);
    ctx.stroke();
    hatches.set(fill, context.createPattern(tile, "repeat"));
  }
  return hatches.get(fill);
}

function englishName(battle) {
  if (!battle.lang || battle.lang === "en") return battle.title;
  return battle.title_source === "vertaald" ? null : battle.title_en;
}

function drawAxes() {
  const { top, y, baseline, x, barWidth } = geometry;
  context.font = "12px 'IBM Plex Sans', system-ui, sans-serif";
  context.textBaseline = "middle";
  context.textAlign = "right";
  for (let i = 0; i <= TICKS; i += 1) {
    const value = (top / TICKS) * i;
    context.strokeStyle = color("--grid");
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(MARGIN.left, Math.round(y(value)) + 0.5);
    context.lineTo(size.width - MARGIN.right, Math.round(y(value)) + 0.5);
    context.stroke();
    context.fillStyle = color("--text-secondary");
    context.fillText(number.format(value), MARGIN.left - 8, y(value));
  }
  context.textAlign = "center";
  context.textBaseline = "top";
  bars.forEach((bar, index) => {
    context.fillStyle = color("--text-secondary");
    context.fillText(bar.name, x(index) + barWidth / 2, baseline + 8);
    if (bar.total > 0) {
      context.fillStyle = color("--text-primary");
      context.textBaseline = "bottom";
      const topOfBar = Math.min(...geometry.rects.filter((r) => r.bar === index).map((r) => r.y0));
      context.fillText(number.format(bar.total), x(index) + barWidth / 2, topOfBar - 4);
      context.textBaseline = "top";
    }
  });
}

function drawBlocks() {
  for (const rect of geometry.rects) {
    const key = bars[rect.bar].segments[rect.segment].benaming;
    const fill = fillOf(key);
    // A gap of surface above each block keeps the blocks apart where there is room for it.
    const height = rect.y1 - rect.y0;
    const top = rect.y0 + (height > GAP * 2 ? GAP : 0);
    context.fillStyle = rect.rough ? hatchOf(fill) : fill;
    context.beginPath();
    if (rect.isTop) context.roundRect(rect.x, top, rect.width, rect.y1 - top, [RADIUS, RADIUS, 0, 0]);
    else context.rect(rect.x, top, rect.width, rect.y1 - top);
    context.fill();
  }
  for (const mark of [chosen, hovered]) {
    if (!mark || mark.segment === null) continue;
    const own = geometry.rects.filter((r) => r.bar === mark.bar && r.segment === mark.segment);
    if (!own.length) continue;
    const y0 = Math.min(...own.map((r) => r.y0));
    const y1 = Math.max(...own.map((r) => r.y1));
    context.strokeStyle = color("--text-primary");
    context.lineWidth = 2;
    context.strokeRect(own[0].x - 1, y0 - 1, own[0].width + 2, y1 - y0 + 2);
  }
}

function draw() {
  const box = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  size = { width: box.width, height: box.height };
  canvas.width = Math.round(box.width * ratio);
  canvas.height = Math.round(box.height * ratio);
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, box.width, box.height);
  if (!bars.length) return;
  geometry = layout(bars, box.width, box.height);
  drawAxes();
  drawBlocks();
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function swatch(key, rough = false) {
  const el = element("span", rough ? "histogram-swatch histogram-swatch-rough" : "histogram-swatch");
  el.style.setProperty("--swatch", fillOf(key));
  return el;
}

function showTooltip(hit, px, py) {
  if (!hit) {
    tooltipEl.hidden = true;
    return;
  }
  const bar = bars[hit.bar];
  tooltipEl.replaceChildren(element("strong", "", `${bar.name}: ${number.format(bar.total)}`));
  for (const segment of [...bar.segments].reverse()) {
    if (!segment.battles.length) continue;
    const name = BENAMINGEN.find((b) => b.key === segment.benaming).name;
    const row = element("div", segment === bar.segments[hit.segment] ? "histogram-tip-row is-hovered" : "histogram-tip-row");
    const rough = segment.rough ? ` (${number.format(segment.rough)} onzeker)` : "";
    row.append(swatch(segment.benaming), element("span", "", `${name}: ${number.format(segment.battles.length)}${rough}`));
    tooltipEl.append(row);
  }
  tooltipEl.hidden = false;
  const left = Math.min(px + 14, size.width - tooltipEl.offsetWidth - 4);
  tooltipEl.style.left = `${Math.max(4, left)}px`;
  tooltipEl.style.top = `${Math.max(4, py - tooltipEl.offsetHeight - 10)}px`;
}

function showList(hit) {
  const bar = bars[hit.bar];
  const segment = bar.segments[hit.segment];
  const name = BENAMINGEN.find((b) => b.key === segment.benaming).name;
  const heading = element("h2", "", `${name} · ${bar.name} (${number.format(segment.battles.length)})`);
  const list = element("ul", "histogram-battles");
  for (const battle of segment.battles) {
    const item = element("li");
    const english = englishName(battle);
    const link = element("a", "", english ?? battle.title);
    link.href = `./${writeView({ battle: battle.title }, "period")}`;
    item.append(link);
    if (english && english !== battle.title) item.append(element("span", "histogram-original", ` ${battle.title}`));
    const when = battle.date_text || `${battle.start} – ${battle.end}`;
    item.append(element("span", "histogram-when", ` · ${durationText(battle)} · ${when}${isRough(battle) ? " · alleen maand of jaar bekend" : ""}`));
    list.append(item);
  }
  listEl.replaceChildren(heading, list);
  listEl.hidden = false;
}

function pointerHit(event) {
  const box = canvas.getBoundingClientRect();
  const px = event.clientX - box.left;
  const py = event.clientY - box.top;
  return { hit: geometry ? hitTest(geometry.rects, bars, size.width, size.height, px, py) : null, px, py };
}

canvas.addEventListener("pointermove", (event) => {
  const { hit, px, py } = pointerHit(event);
  const same = hit?.bar === hovered?.bar && hit?.segment === hovered?.segment;
  hovered = hit;
  canvas.style.cursor = hit?.segment != null ? "pointer" : "default";
  if (!same) draw();
  showTooltip(hit, px, py);
});
canvas.addEventListener("pointerleave", () => {
  hovered = null;
  tooltipEl.hidden = true;
  draw();
});
canvas.addEventListener("click", (event) => {
  const { hit } = pointerHit(event);
  if (hit?.segment == null) return;
  chosen = hit;
  draw();
  showList(hit);
  listEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

function renderLegend(battles) {
  const counts = new Map(BENAMINGEN.map(({ key }) => [key, 0]));
  for (const bar of bars) for (const segment of bar.segments) counts.set(segment.benaming, counts.get(segment.benaming) + segment.battles.length);
  const legend = document.getElementById("histogram-legend");
  legend.replaceChildren(...BENAMINGEN.map(({ key, name }) => {
    const item = element("span", "histogram-legend-item");
    item.append(swatch(key), element("span", "", `${name} (${number.format(counts.get(key))})`));
    return item;
  }));
  const rough = element("span", "histogram-legend-item");
  rough.append(swatch("ander", true), element("span", "", "gearceerd: alleen maand of jaar bekend"));
  legend.append(rough);
  const roughCount = battles.filter(isRough).length;
  document.getElementById("histogram-count").textContent =
    `${number.format(battles.length)} Veldslagen, waarvan ${number.format(roughCount)} met alleen een maand of jaar (gearceerd).`;
}

function renderTable() {
  const head = element("tr");
  head.append(element("th", "", "Duur"), ...BENAMINGEN.map(({ name }) => element("th", "", name)), element("th", "", "Totaal"));
  head.querySelectorAll("th").forEach((th) => th.setAttribute("scope", "col"));
  document.getElementById("histogram-head").replaceChildren(head);
  document.getElementById("histogram-rows").replaceChildren(...bars.map((bar) => {
    const row = element("tr");
    const label = element("th", "", bar.name);
    label.setAttribute("scope", "row");
    row.append(label, ...bar.segments.map((s) => element("td", "", number.format(s.battles.length))), element("td", "", number.format(bar.total)));
    return row;
  }));
}

async function start() {
  try {
    const response = await fetch(BATTLES_URL);
    if (!response.ok) throw new Error(`${BATTLES_URL}: ${response.status}`);
    const battles = await response.json();
    bars = histogram(battles);
    renderLegend(battles);
    renderTable();
    draw();
  } catch (error) {
    console.error(error);
    document.getElementById("histogram-count").textContent = "De Veldslagen konden niet worden geladen.";
  }
}

new ResizeObserver(() => draw()).observe(canvas);
start();

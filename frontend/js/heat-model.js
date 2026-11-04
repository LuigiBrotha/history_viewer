import { turboColor } from "./color-ramp.js";
import { inPeriod } from "./status-map.js";

export const CELL_DEGREES = 0.5;
export const COLUMNS = 720;
export const ROWS = 360;

const STEP_DEGREES = CELL_DEGREES / 2;
const KERNEL = [[-1, -1, 1], [0, -1, 2], [1, -1, 1], [-1, 0, 2], [0, 0, 4], [1, 0, 2], [-1, 1, 1], [0, 1, 2], [1, 1, 1]];
const KERNEL_TOTAL = 16;
const SCALE_PERCENTILE = 0.99;
const MIN_ALPHA = 60;
const MAX_ALPHA = 220;

function clampIndex(value, size) {
  return Math.min(size - 1, Math.max(0, value));
}

export function cellIndex(lat, lng) {
  const row = clampIndex(Math.floor((lat + 90) / CELL_DEGREES), ROWS);
  const column = clampIndex(Math.floor((lng + 180) / CELL_DEGREES), COLUMNS);
  return row * COLUMNS + column;
}

// Every cell a patrol's drawn routes pass through. A patrol counts once per cell, so a
// boat circling in one area does not outweigh many boats passing through it.
export function patrolCells(patrol) {
  const cells = new Set();
  for (const leg of patrol.legs ?? []) {
    if (!leg.path || (leg.status !== "ok" && leg.status !== "suspect")) {
      continue;
    }
    cells.add(cellIndex(leg.path[0][0], leg.path[0][1]));
    for (let i = 1; i < leg.path.length; i++) {
      const [lat0, lng0] = leg.path[i - 1];
      const [lat1, lng1] = leg.path[i];
      const steps = Math.ceil(Math.max(Math.abs(lat1 - lat0), Math.abs(lng1 - lng0)) / STEP_DEGREES);
      for (let step = 1; step <= steps; step++) {
        const fraction = step / steps;
        cells.add(cellIndex(lat0 + (lat1 - lat0) * fraction, lng0 + (lng1 - lng0) * fraction));
      }
    }
  }
  return cells;
}

export function densityGrid(entries, from, to) {
  const grid = new Float64Array(COLUMNS * ROWS);
  let patrols = 0;
  for (const { patrol, cells } of entries) {
    if (inPeriod(patrol, from, to)) {
      patrols += 1;
      for (const cell of cells) {
        grid[cell] += 1;
      }
    }
  }
  return { grid, patrols };
}

export function smooth(grid) {
  const smoothed = new Float64Array(grid.length);
  for (let cell = 0; cell < grid.length; cell++) {
    const value = grid[cell];
    if (value === 0) {
      continue;
    }
    const row = Math.floor(cell / COLUMNS);
    const column = cell % COLUMNS;
    for (const [dx, dy, weight] of KERNEL) {
      const targetRow = row + dy;
      if (targetRow >= 0 && targetRow < ROWS) {
        smoothed[targetRow * COLUMNS + ((column + dx + COLUMNS) % COLUMNS)] += (value * weight) / KERNEL_TOTAL;
      }
    }
  }
  return smoothed;
}

// The value that gets the ramp's top colour. Bases see nearly every patrol pass, and
// measuring against them would leave the whole ocean in one low colour.
export function scaleMax(grid) {
  const values = grid.filter((value) => value > 0).sort();
  if (values.length === 0) {
    return 0;
  }
  return values[Math.min(values.length - 1, Math.floor(values.length * SCALE_PERCENTILE))];
}

const RAMP = Array.from({ length: 256 }, (_, i) => {
  const hex = turboColor(i / 255);
  return [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16));
});

// A square root keeps quieter areas visible beside the few very busy ones.
export function heatColor(value, max) {
  if (value <= 0 || max <= 0) {
    return [0, 0, 0, 0];
  }
  const strength = Math.sqrt(Math.min(1, value / max));
  const [red, green, blue] = RAMP[Math.round(strength * 255)];
  return [red, green, blue, Math.round(MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * strength)];
}

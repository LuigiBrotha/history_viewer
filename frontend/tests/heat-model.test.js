import { test } from "node:test";
import assert from "node:assert/strict";

import {
  COLUMNS,
  ROWS,
  cellIndex,
  patrolCells,
  densityGrid,
  smooth,
  heatColor,
  scaleMax,
} from "../js/heat-model.js";

const leg = (path, status = "ok") => ({ status, path });

test("cellIndex maps a coordinate to a half-degree cell", () => {
  assert.equal(cellIndex(0, 0), cellIndex(0.1, 0.1));
  assert.notEqual(cellIndex(0, 0), cellIndex(0, 0.6));
  assert.notEqual(cellIndex(0, 0), cellIndex(0.6, 0));
});

test("cellIndex keeps the edges of the world inside the grid", () => {
  assert.ok(cellIndex(90, 180) < COLUMNS * ROWS);
  assert.ok(cellIndex(-90, -180) >= 0);
});

test("patrolCells walks along a leg instead of only marking its ends", () => {
  const cells = patrolCells({ legs: [leg([[50, -10], [50, -5]])] });
  assert.ok(cells.has(cellIndex(50, -7.5)));
  assert.equal(cells.size, 11);
});

test("patrolCells counts a cell once when a patrol crosses it twice", () => {
  const cells = patrolCells({ legs: [leg([[50, -10], [50, -9]]), leg([[50, -9], [50, -10]])] });
  assert.equal(cells.size, 3);
});

test("patrolCells includes suspect legs but no leg without a route", () => {
  const cells = patrolCells({
    legs: [
      leg([[50, -10], [50, -10]], "suspect"),
      leg(null, "on_land"),
      leg(null, "not_computed"),
    ],
  });
  assert.deepEqual([...cells], [cellIndex(50, -10)]);
});

test("patrolCells handles a patrol without legs", () => {
  assert.equal(patrolCells({ points: [] }).size, 0);
});

test("densityGrid counts patrols overlapping the period", () => {
  const cell = cellIndex(50, -10);
  const entries = [
    { patrol: { departure_date: "1940-01-01", arrival_date: "1940-02-01", points: [] }, cells: new Set([cell]) },
    { patrol: { departure_date: "1940-01-15", arrival_date: "1940-03-01", points: [] }, cells: new Set([cell]) },
    { patrol: { departure_date: "1943-01-01", arrival_date: "1943-02-01", points: [] }, cells: new Set([cell]) },
  ];
  const { grid, patrols } = densityGrid(entries, "1940-01-01", "1940-12-31");
  assert.equal(grid[cell], 2);
  assert.equal(patrols, 2);
});

test("densityGrid without a period counts everything", () => {
  const cell = cellIndex(50, -10);
  const entries = [{ patrol: { points: [] }, cells: new Set([cell]) }];
  assert.equal(densityGrid(entries, null, null).grid[cell], 1);
});

test("smooth spreads a value to its neighbours and keeps the total close", () => {
  const grid = new Float64Array(COLUMNS * ROWS);
  const row = Math.floor(ROWS / 2);
  const middle = row * COLUMNS + 100;
  grid[middle] = 9;
  const smoothed = smooth(grid);
  assert.equal(smoothed[middle + 1], smoothed[middle - 1]);
  assert.ok(smoothed[middle] > smoothed[middle + 1]);
  assert.ok(smoothed[middle + 1] > 0);
  const total = smoothed.reduce((sum, value) => sum + value, 0);
  assert.ok(Math.abs(total - 9) < 1e-9);
});

test("heatColor is transparent at nothing and strongest at the maximum", () => {
  assert.equal(heatColor(0, 10)[3], 0);
  const low = heatColor(0.5, 10);
  const high = heatColor(10, 10);
  assert.ok(high[3] > low[3]);
  assert.ok(low[3] > 0);
});

test("heatColor uses the Turbo ramp's highest colour at the maximum", () => {
  const [red, green, blue] = heatColor(10, 10);
  assert.ok(red > 100 && green < 30 && blue < 30);
});

test("heatColor with an empty grid is transparent", () => {
  assert.equal(heatColor(0, 0)[3], 0);
});

test("scaleMax ignores a few extreme cells, so busy ports do not wash out the sea", () => {
  const grid = new Float64Array(1000);
  for (let i = 0; i < 995; i++) {
    grid[i] = 10;
  }
  grid[999] = 500;
  assert.equal(scaleMax(grid), 10);
});

test("scaleMax uses the only values there are in a small selection", () => {
  const grid = new Float64Array(100);
  grid[3] = 4;
  assert.equal(scaleMax(grid), 4);
});

test("scaleMax of an empty grid is zero", () => {
  assert.equal(scaleMax(new Float64Array(10)), 0);
});

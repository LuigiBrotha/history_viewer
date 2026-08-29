# U-boat Route Map — Leaflet Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser-based Leaflet map with a time slider, consuming the existing read-only
uboat.net API, so a user can travel through the war and see which U-boats were on patrol on a
given date, and follow one boat's route.

**Architecture:** A new top-level `frontend/` directory: vanilla HTML/CSS/JS loaded as ES modules,
no build step, no npm install. Leaflet loads from its official CDN as a classic script (global
`L`). On page load the app fetches the entire boat list and patrol-route dataset once from the
existing FastAPI endpoints and does all filtering, date-range computation, and position
interpolation client-side, in memory. A small change to the existing backend (`app/main.py`) adds
CORS support, since the frontend runs on a different origin/port.

**Tech Stack:** Vanilla JavaScript (ES modules), Leaflet.js (CDN), plain CSS, Node's built-in
`node:test`/`node:assert` for unit tests (no test framework, no build step). Backend: FastAPI +
`fastapi.middleware.cors.CORSMiddleware` (one new dependency-free stdlib-adjacent import, already
bundled with FastAPI).

**Spec:** `docs/superpowers/specs/2026-08-29-uboat-leaflet-frontend-design.md`

## Global Constraints

- Stack: vanilla HTML/CSS/JS + Leaflet via CDN. No build step. `frontend/package.json` exists
  only to declare `"type": "module"` so Node's test runner resolves `import`/`export` syntax —
  it has no dependencies and `npm install` is never required.
- Location: everything lives under a new top-level `frontend/` directory. It is not served by
  FastAPI (no `StaticFiles` mount) — run it with any static file server, e.g.
  `python3 -m http.server 5500 --directory frontend`.
- Data loading: fetch `GET /api/uboats/boten` and `GET /api/uboats/routes` exactly once, on page
  load. All filtering, date-range derivation, and position interpolation happens client-side in
  memory. No new backend endpoints, no pagination.
- CORS: `app/main.py` needs `fastapi.middleware.cors.CORSMiddleware` added — permissive
  (`allow_origins=["*"]`), GET only. This is the one required backend change and nothing else in
  `app/` changes.
- "Active on date X": a patrol is active on a date only if that date falls between its first and
  last **dated** route point (inclusive). Undated points are never used as interpolation
  endpoints, though they still render as part of the static full route line when a boat is
  followed. A patrol with zero dated points never appears in the date-based active view.
- Position interpolation: linear interpolation (lat/lng) between the two dated route points
  immediately surrounding the target date. An exact date match on a dated point uses that point's
  coordinates directly, no interpolation.
- Timeline: a draggable date slider (day granularity, bounded by the min/max dated route point
  across all loaded patrols) plus a play/pause auto-advance control at a fixed speed (500ms per
  simulated day) — no speed selector.
- Layout: full-screen map, collapsible sidebar listing boats active on the current date
  (click-to-follow), slider docked at the bottom of the map.
- Follow mode: clicking a boat (sidebar or map marker) highlights its full route polyline,
  centers/zooms the map on it, dims/hides other boats' markers, and shows a "back to full view"
  control.
- Testing: `js/time-model.js`'s pure interpolation/active-boat logic gets full unit test coverage
  via Node's built-in `node:test`/`node:assert` (`node --test <file>`), no framework. Every other
  module (`map.js`, `timeline.js`, `sidebar.js`, `main.js`, `index.html`, CSS) is UI wiring —
  verified manually in a browser, per this project's own convention for frontend changes and per
  the spec's explicit testing decision. There is no existing UI test harness in this repo to
  extend.
- API base URL is a hardcoded constant in `js/api.js` (`http://localhost:8000`) — no environment
  config system; this is a local dev tool, not a deployed multi-environment app.
- Real data is already available for manual verification throughout: `uboats.db` at the repo root
  (10 boats, 43 patrol routes, 1067 route points — a genuine crawl result, not a fixture).

---

### Task 1: Project scaffolding, page shell, and backend CORS

**Files:**
- Modify: `app/main.py`
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/css/style.css`

**Interfaces:**
- Produces: the page shell's DOM element IDs that every later task's JS relies on: `#map`,
  `#sidebar`, `#boat-date-label`, `#boat-list`, `#reset-follow`, `#timeline`, `#play-pause`,
  `#date-slider`, `#date-display`, `#toggle-sidebar`. Also establishes that `L` (Leaflet) is a
  global available to any classic or module script loaded after it.

- [ ] **Step 1: Add CORS middleware to the backend**

Open `app/main.py`. It currently reads:

```python
import asyncio

import uvicorn
import wireup.integration.fastapi
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import settings
from app.core.container import container
from app.core.database import engine
from app.services.storage.database import init_models
from fastapi import FastAPI

asyncio.run(init_models(engine))

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    debug=settings.DEBUG,
)

with async_container_force_sync_scope(container) as scope:
    request_handler_registry = scope.get(RequestHandlerRegistry)
    handlers = list(request_handler_registry)

wireup.integration.fastapi.setup(container, app, class_based_handlers=handlers)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

Replace it with (adds one import and one `app.add_middleware(...)` call right after `app` is
created; nothing else changes):

```python
import asyncio

import uvicorn
import wireup.integration.fastapi
from fastapi.middleware.cors import CORSMiddleware
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import settings
from app.core.container import container
from app.core.database import engine
from app.services.storage.database import init_models
from fastapi import FastAPI

asyncio.run(init_models(engine))

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

with async_container_force_sync_scope(container) as scope:
    request_handler_registry = scope.get(RequestHandlerRegistry)
    handlers = list(request_handler_registry)

wireup.integration.fastapi.setup(container, app, class_based_handlers=handlers)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Verify the backend still boots and the existing suite still passes**

Run: `poetry run pytest -q`
Expected: all existing tests still pass (65 passed, unchanged — this is a middleware addition,
not a behavior change to any handler).

- [ ] **Step 3: Create `frontend/package.json`**

```json
{
  "name": "uboat-route-map",
  "private": true,
  "type": "module"
}
```

This has no dependencies and requires no `npm install` — it exists solely so Node's test runner
treats `.js` files under `frontend/` as ES modules (`import`/`export` syntax) in later tasks.

- [ ] **Step 4: Create `frontend/css/style.css`**

```css
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: system-ui, sans-serif;
}

#app {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

#map {
  flex: 1;
  width: 100%;
  background: #dde;
}

#sidebar {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 280px;
  max-height: calc(100vh - 90px);
  overflow-y: auto;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  padding: 12px;
  box-sizing: border-box;
  z-index: 1000;
  border-radius: 6px;
  transition: transform 0.2s ease;
}

#sidebar.collapsed {
  transform: translateX(310px);
}

#sidebar h2 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

#boat-date-label {
  font-size: 13px;
  color: #444;
  margin-bottom: 8px;
}

#boat-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

#boat-list li {
  padding: 6px 4px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
  font-size: 14px;
}

#boat-list li:hover {
  background: #f0f0f0;
}

#boat-list li.following {
  font-weight: bold;
  background: #e0f0ff;
}

#reset-follow {
  margin-top: 8px;
  width: 100%;
}

#toggle-sidebar {
  position: absolute;
  top: 12px;
  right: 300px;
  z-index: 1001;
}

#timeline {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #222;
  color: white;
}

#date-slider {
  flex: 1;
}

#play-pause {
  font-size: 18px;
  cursor: pointer;
  background: none;
  border: 1px solid white;
  color: white;
  border-radius: 4px;
  padding: 4px 10px;
}

#date-display {
  min-width: 90px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>U-boat Route Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="css/style.css" />
</head>
<body>
  <div id="app">
    <div id="map"></div>

    <button id="toggle-sidebar" title="Zijbalk in/uitklappen">☰</button>

    <aside id="sidebar">
      <h2>Actieve boten</h2>
      <div id="boat-date-label"></div>
      <ul id="boat-list"></ul>
      <button id="reset-follow" hidden>Terug naar volledige weergave</button>
    </aside>

    <div id="timeline">
      <button id="play-pause">▶</button>
      <input type="range" id="date-slider" min="0" max="0" value="0" step="1" />
      <span id="date-display"></span>
    </div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script type="module" src="js/main.js"></script>
</body>
</html>
```

Note: `js/main.js` does not exist until Task 7. Until then, loading this page shows the shell
with an empty gray `#map` box and no crash — the `<script type="module" src="js/main.js">` tag
simply fails to load (404) harmlessly, which is expected at this point in the plan.

- [ ] **Step 6: Manually verify the shell and CORS**

Start the backend (it now has the real crawled data at the repo root):

```bash
cd /home/scout/PycharmProjects/uboats
poetry run uvicorn app.main:app --port 8000
```

In a second terminal, serve the frontend:

```bash
cd /home/scout/PycharmProjects/uboats/frontend
python3 -m http.server 5500
```

Open `http://localhost:5500` in a browser. Expected: the page loads with a light-gray full-screen
box (`#map`), a sidebar panel top-right with "Actieve boten" and an empty list, and a dark
timeline bar at the bottom with a play button, a slider, and an empty date display. No visible
layout breakage.

Open the browser's developer console and run:

```js
typeof L
```

Expected: `"object"` (confirms Leaflet loaded from the CDN).

Then, still in the console, run:

```js
fetch("http://localhost:8000/api/uboats/boten").then(r => r.json()).then(console.log)
```

Expected: a resolved array of real boat objects (e.g. `{slug: "u1", number: "U-1", ...}`) logged
to the console, with **no CORS error** in the console. If a CORS error appears, Step 1 was not
applied correctly — re-check `app/main.py`.

Stop both servers (`Ctrl+C` in each terminal) once confirmed.

- [ ] **Step 7: Commit**

```bash
git add app/main.py frontend/package.json frontend/index.html frontend/css/style.css
git commit -m "Add frontend page shell and enable CORS for local dev"
```

---

### Task 2: API fetch wrapper (`js/api.js`)

**Files:**
- Create: `frontend/js/api.js`
- Test: `frontend/tests/api.test.js`

**Interfaces:**
- Produces: `async function fetchBoats() -> Promise<Array>` (raw JSON array from
  `GET /api/uboats/boten`), `async function fetchRoutes() -> Promise<Array>` (raw JSON array from
  `GET /api/uboats/routes`). Both reject if the response is not `ok`. Task 7's `main.js` calls
  both once on startup.

- [ ] **Step 1: Write the failing test**

`frontend/tests/api.test.js`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";

import { fetchBoats, fetchRoutes } from "../js/api.js";

test("fetchBoats calls the boten endpoint and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [{ slug: "u1" }] };
  };

  const result = await fetchBoats();

  assert.deepEqual(calls, ["http://localhost:8000/api/uboats/boten"]);
  assert.deepEqual(result, [{ slug: "u1" }]);
});

test("fetchRoutes calls the routes endpoint and returns parsed JSON", async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return { ok: true, json: async () => [{ boat_slug: "u1" }] };
  };

  const result = await fetchRoutes();

  assert.deepEqual(calls, ["http://localhost:8000/api/uboats/routes"]);
  assert.deepEqual(result, [{ boat_slug: "u1" }]);
});

test("fetchBoats rejects when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 500 });

  await assert.rejects(() => fetchBoats(), /Failed to fetch boats: 500/);
});

test("fetchRoutes rejects when the response is not ok", async () => {
  globalThis.fetch = async () => ({ ok: false, status: 404 });

  await assert.rejects(() => fetchRoutes(), /Failed to fetch routes: 404/);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test frontend/tests/api.test.js`
Expected: FAIL — cannot find module `../js/api.js` (the file doesn't exist yet).

- [ ] **Step 3: Write `frontend/js/api.js`**

```javascript
const API_BASE = "http://localhost:8000";

export async function fetchBoats() {
  const response = await fetch(`${API_BASE}/api/uboats/boten`);
  if (!response.ok) {
    throw new Error(`Failed to fetch boats: ${response.status}`);
  }
  return response.json();
}

export async function fetchRoutes() {
  const response = await fetch(`${API_BASE}/api/uboats/routes`);
  if (!response.ok) {
    throw new Error(`Failed to fetch routes: ${response.status}`);
  }
  return response.json();
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test frontend/tests/api.test.js`
Expected: 4 tests passing.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/api.js frontend/tests/api.test.js
git commit -m "Add API fetch wrapper for boats and routes endpoints"
```

---

### Task 3: Time model — active-boat and interpolation logic (`js/time-model.js`)

This is the one module with real logic worth testing in isolation — everything else in this plan
is UI wiring. Get this one right and well-covered.

**Files:**
- Create: `frontend/js/time-model.js`
- Test: `frontend/tests/time-model.test.js`

**Interfaces:**
- Consumes: nothing from other frontend modules — pure functions over plain data shaped like the
  API's `PatrolRouteOut`/`RoutePointOut` JSON (`{boat_slug, boat_number, external_id, points: [{sequence, lat, lng, date}]}`,
  where `date` is either an ISO `"YYYY-MM-DD"` string or `null`).
- Produces: `parseDate(dateStr) -> Date | null`, `datedPoints(patrol) -> Array<point>`,
  `interpolatePosition(patrol, targetDate) -> {lat, lng} | null`,
  `activeBoatsOnDate(routes, targetDate) -> Array<{boatSlug, boatNumber, externalId, lat, lng, patrol}>`,
  `dateRange(routes) -> {min: Date, max: Date} | null`. Tasks 4, 6, and 7 call
  `activeBoatsOnDate`/`dateRange`/`interpolatePosition` directly.

- [ ] **Step 1: Write the failing tests**

`frontend/tests/time-model.test.js`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  parseDate,
  datedPoints,
  interpolatePosition,
  activeBoatsOnDate,
  dateRange,
} from "../js/time-model.js";

test("parseDate parses a YYYY-MM-DD string as UTC midnight", () => {
  const d = parseDate("1940-06-18");
  assert.equal(d.getUTCFullYear(), 1940);
  assert.equal(d.getUTCMonth(), 5);
  assert.equal(d.getUTCDate(), 18);
});

test("parseDate returns null for null, undefined, and empty input", () => {
  assert.equal(parseDate(null), null);
  assert.equal(parseDate(undefined), null);
  assert.equal(parseDate(""), null);
});

test("datedPoints filters out points with a null date, preserving order", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 1, lng: 1, date: "2020-01-01" },
      { sequence: 1, lat: 2, lng: 2, date: null },
      { sequence: 2, lat: 3, lng: 3, date: "2020-01-03" },
    ],
  };

  const dated = datedPoints(patrol);

  assert.equal(dated.length, 2);
  assert.deepEqual(dated.map((p) => p.sequence), [0, 2]);
});

test("interpolatePosition returns exact coordinates on an exact date match", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 54.0, lng: 10.0, date: "1940-06-18" },
      { sequence: 1, lat: 56.0, lng: 12.0, date: "1940-06-20" },
    ],
  };

  const result = interpolatePosition(patrol, parseDate("1940-06-18"));

  assert.deepEqual(result, { lat: 54.0, lng: 10.0 });
});

test("interpolatePosition linearly interpolates halfway between two dated points", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 54.0, lng: 10.0, date: "1940-06-18" },
      { sequence: 1, lat: 56.0, lng: 12.0, date: "1940-06-20" },
    ],
  };

  const result = interpolatePosition(patrol, parseDate("1940-06-19"));

  assert.deepEqual(result, { lat: 55.0, lng: 11.0 });
});

test("interpolatePosition ignores an undated point sitting between two dated points", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
      { sequence: 1, lat: 99, lng: 99, date: null },
      { sequence: 2, lat: 4, lng: 8, date: "2020-01-03" },
    ],
  };

  const result = interpolatePosition(patrol, parseDate("2020-01-02"));

  assert.deepEqual(result, { lat: 2, lng: 4 });
});

test("interpolatePosition returns null before the patrol's first dated point", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 54.0, lng: 10.0, date: "1940-06-18" },
      { sequence: 1, lat: 56.0, lng: 12.0, date: "1940-06-20" },
    ],
  };

  assert.equal(interpolatePosition(patrol, parseDate("1940-06-17")), null);
});

test("interpolatePosition returns null after the patrol's last dated point", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 54.0, lng: 10.0, date: "1940-06-18" },
      { sequence: 1, lat: 56.0, lng: 12.0, date: "1940-06-20" },
    ],
  };

  assert.equal(interpolatePosition(patrol, parseDate("1940-06-21")), null);
});

test("interpolatePosition returns null for a patrol with zero dated points", () => {
  const patrol = {
    points: [
      { sequence: 0, lat: 1, lng: 1, date: null },
      { sequence: 1, lat: 2, lng: 2, date: null },
    ],
  };

  assert.equal(interpolatePosition(patrol, parseDate("2020-01-01")), null);
});

test("interpolatePosition returns the single point for a patrol with exactly one dated point", () => {
  const patrol = { points: [{ sequence: 0, lat: 5, lng: 5, date: "2020-01-01" }] };

  const result = interpolatePosition(patrol, parseDate("2020-01-01"));

  assert.deepEqual(result, { lat: 5, lng: 5 });
});

test("activeBoatsOnDate includes only patrols active on the given date", () => {
  const routes = [
    {
      boat_slug: "u1",
      boat_number: "U-1",
      external_id: "patrol_1",
      points: [
        { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
        { sequence: 1, lat: 10, lng: 10, date: "2020-01-05" },
      ],
    },
    {
      boat_slug: "u2",
      boat_number: "U-2",
      external_id: "patrol_2",
      points: [
        { sequence: 0, lat: 20, lng: 20, date: "2020-02-01" },
        { sequence: 1, lat: 30, lng: 30, date: "2020-02-05" },
      ],
    },
  ];

  const active = activeBoatsOnDate(routes, parseDate("2020-01-03"));

  assert.equal(active.length, 1);
  assert.equal(active[0].boatSlug, "u1");
  assert.equal(active[0].boatNumber, "U-1");
  assert.equal(active[0].externalId, "patrol_1");
});

test("dateRange returns the min and max dated point across all routes, ignoring undated points", () => {
  const routes = [
    {
      points: [
        { sequence: 0, lat: 0, lng: 0, date: "2020-03-01" },
        { sequence: 1, lat: 1, lng: 1, date: null },
      ],
    },
    {
      points: [
        { sequence: 0, lat: 0, lng: 0, date: "2020-01-01" },
        { sequence: 1, lat: 1, lng: 1, date: "2020-05-01" },
      ],
    },
  ];

  const range = dateRange(routes);

  assert.equal(range.min.getTime(), parseDate("2020-01-01").getTime());
  assert.equal(range.max.getTime(), parseDate("2020-05-01").getTime());
});

test("dateRange returns null when no route has any dated point", () => {
  const routes = [{ points: [{ sequence: 0, lat: 0, lng: 0, date: null }] }];

  assert.equal(dateRange(routes), null);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test frontend/tests/time-model.test.js`
Expected: FAIL — cannot find module `../js/time-model.js`.

- [ ] **Step 3: Write `frontend/js/time-model.js`**

```javascript
export function parseDate(dateStr) {
  if (!dateStr) {
    return null;
  }
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

export function datedPoints(patrol) {
  return patrol.points.filter((point) => point.date !== null && point.date !== undefined);
}

export function interpolatePosition(patrol, targetDate) {
  const dated = datedPoints(patrol);
  if (dated.length === 0) {
    return null;
  }

  const targetTime = targetDate.getTime();
  const firstTime = parseDate(dated[0].date).getTime();
  const lastTime = parseDate(dated[dated.length - 1].date).getTime();

  if (targetTime < firstTime || targetTime > lastTime) {
    return null;
  }

  for (let i = 0; i < dated.length - 1; i++) {
    const t0 = parseDate(dated[i].date).getTime();
    const t1 = parseDate(dated[i + 1].date).getTime();

    if (targetTime === t0) {
      return { lat: dated[i].lat, lng: dated[i].lng };
    }
    if (targetTime === t1) {
      return { lat: dated[i + 1].lat, lng: dated[i + 1].lng };
    }
    if (targetTime > t0 && targetTime < t1) {
      const fraction = (targetTime - t0) / (t1 - t0);
      return {
        lat: dated[i].lat + (dated[i + 1].lat - dated[i].lat) * fraction,
        lng: dated[i].lng + (dated[i + 1].lng - dated[i].lng) * fraction,
      };
    }
  }

  // dated.length === 1: firstTime === lastTime === targetTime, already checked above.
  return { lat: dated[0].lat, lng: dated[0].lng };
}

export function activeBoatsOnDate(routes, targetDate) {
  const active = [];
  for (const patrol of routes) {
    const position = interpolatePosition(patrol, targetDate);
    if (position !== null) {
      active.push({
        boatSlug: patrol.boat_slug,
        boatNumber: patrol.boat_number,
        externalId: patrol.external_id,
        lat: position.lat,
        lng: position.lng,
        patrol,
      });
    }
  }
  return active;
}

export function dateRange(routes) {
  let min = null;
  let max = null;
  for (const patrol of routes) {
    for (const point of datedPoints(patrol)) {
      const t = parseDate(point.date).getTime();
      if (min === null || t < min) {
        min = t;
      }
      if (max === null || t > max) {
        max = t;
      }
    }
  }
  if (min === null) {
    return null;
  }
  return { min: new Date(min), max: new Date(max) };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test frontend/tests/time-model.test.js`
Expected: 14 tests passing.

- [ ] **Step 5: Commit**

```bash
git add frontend/js/time-model.js frontend/tests/time-model.test.js
git commit -m "Add pure time-model module: interpolation and active-boat logic"
```

---

### Task 4: Leaflet map rendering (`js/map.js`)

UI wiring — no unit tests. Manually verified in Task 7 once `main.js` wires everything together
(this module has no standalone entry point of its own, so there is nothing meaningful to verify
in isolation before then; note that explicitly and move on).

**Files:**
- Create: `frontend/js/map.js`

**Interfaces:**
- Consumes: the global `L` (Leaflet, loaded via CDN in `index.html`), and the
  `{boatSlug, boatNumber, externalId, lat, lng, patrol}` shape produced by Task 3's
  `activeBoatsOnDate`.
- Produces: `createMap(containerId) -> mapState` (an object `{map, activeBoatsLayer, followedRouteLayer}`),
  `renderActiveBoats(mapState, activeBoats, onBoatClick)`,
  `renderFollowedRoute(mapState, patrol, currentPosition)`, `clearFollowedRoute(mapState)`. Task 7's
  `main.js` calls all four.

- [ ] **Step 1: Write `frontend/js/map.js`**

```javascript
export function createMap(containerId) {
  const map = L.map(containerId).setView([54.5, 8.0], 5);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const activeBoatsLayer = L.layerGroup().addTo(map);
  const followedRouteLayer = L.layerGroup().addTo(map);

  return { map, activeBoatsLayer, followedRouteLayer };
}

export function renderActiveBoats(mapState, activeBoats, onBoatClick) {
  mapState.activeBoatsLayer.clearLayers();

  for (const boat of activeBoats) {
    const marker = L.circleMarker([boat.lat, boat.lng], {
      radius: 6,
      color: "#0077cc",
      fillColor: "#0077cc",
      fillOpacity: 0.85,
    });
    marker.bindTooltip(boat.boatNumber);
    marker.on("click", () => onBoatClick(boat.boatSlug));
    marker.addTo(mapState.activeBoatsLayer);
  }
}

export function renderFollowedRoute(mapState, patrol, currentPosition) {
  mapState.followedRouteLayer.clearLayers();

  const latLngs = patrol.points.map((point) => [point.lat, point.lng]);
  const polyline = L.polyline(latLngs, { color: "#cc3300", weight: 3 });
  polyline.addTo(mapState.followedRouteLayer);

  if (currentPosition !== null) {
    L.circleMarker([currentPosition.lat, currentPosition.lng], {
      radius: 8,
      color: "#cc3300",
      fillColor: "#ffcc00",
      fillOpacity: 1,
    }).addTo(mapState.followedRouteLayer);
  }

  mapState.map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
}

export function clearFollowedRoute(mapState) {
  mapState.followedRouteLayer.clearLayers();
}
```

- [ ] **Step 2: Confirm the file has no syntax errors**

Run: `node --check frontend/js/map.js`
Expected: no output (exit code 0). This module depends on the browser-global `L` and cannot be
exercised standalone in Node — `--check` only parses it. Full behavior is verified manually with
the rest of the app wired up in Task 7's manual verification step.

- [ ] **Step 3: Commit**

```bash
git add frontend/js/map.js
git commit -m "Add Leaflet map rendering: active boats and followed-route layers"
```

---

### Task 5: Timeline slider and play/pause (`js/timeline.js`)

UI wiring — no unit tests, verified manually in Task 7 alongside the rest of the app.

**Files:**
- Create: `frontend/js/timeline.js`

**Interfaces:**
- Consumes: the `#date-slider`, `#play-pause`, `#date-display` DOM elements from Task 1's
  `index.html`, and a `{min: Date, max: Date}` range from Task 3's `dateRange`.
- Produces: `initTimeline({sliderEl, playPauseEl, dateDisplayEl, minDate, maxDate, onDateChange}) -> {stop}`.
  Calls `onDateChange(date: Date)` once immediately on init and again on every slider move or
  auto-advance tick. Task 7's `main.js` calls this once during startup.

- [ ] **Step 1: Write `frontend/js/timeline.js`**

```javascript
const DAY_MS = 24 * 60 * 60 * 1000;
const TICK_MS = 500;

export function initTimeline({ sliderEl, playPauseEl, dateDisplayEl, minDate, maxDate, onDateChange }) {
  const totalDays = Math.round((maxDate.getTime() - minDate.getTime()) / DAY_MS);
  sliderEl.min = "0";
  sliderEl.max = String(totalDays);
  sliderEl.value = "0";

  let playing = false;
  let intervalId = null;

  function dateForValue(value) {
    return new Date(minDate.getTime() + Number(value) * DAY_MS);
  }

  function formatDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function emitDate() {
    const date = dateForValue(sliderEl.value);
    dateDisplayEl.textContent = formatDate(date);
    onDateChange(date);
  }

  function stop() {
    playing = false;
    playPauseEl.textContent = "▶";
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  function play() {
    playing = true;
    playPauseEl.textContent = "⏸";
    intervalId = setInterval(() => {
      const next = Number(sliderEl.value) + 1;
      if (next > totalDays) {
        stop();
        return;
      }
      sliderEl.value = String(next);
      emitDate();
    }, TICK_MS);
  }

  sliderEl.addEventListener("input", () => {
    if (playing) {
      stop();
    }
    emitDate();
  });

  playPauseEl.addEventListener("click", () => {
    if (playing) {
      stop();
    } else {
      play();
    }
  });

  emitDate();

  return { stop };
}
```

- [ ] **Step 2: Confirm the file has no syntax errors**

Run: `node --check frontend/js/timeline.js`
Expected: no output (exit code 0).

- [ ] **Step 3: Commit**

```bash
git add frontend/js/timeline.js
git commit -m "Add timeline slider with play/pause auto-advance"
```

---

### Task 6: Sidebar boat list (`js/sidebar.js`)

UI wiring — no unit tests, verified manually in Task 7 alongside the rest of the app.

**Files:**
- Create: `frontend/js/sidebar.js`

**Interfaces:**
- Consumes: the `#boat-list` and `#boat-date-label` DOM elements from Task 1's `index.html`, the
  `{boatSlug, boatNumber, externalId, ...}` array shape produced by Task 3's `activeBoatsOnDate`,
  and an optional `Map<slug, BoatSummary>` (from the raw `GET /api/uboats/boten` objects, keyed by
  `.slug`) used to show each boat's `type` alongside its number.
- Produces: `renderBoatList({listEl, activeBoats, followedSlug, onBoatSelect, boatsBySlug})`,
  `updateDateLabel(labelEl, date)`. Task 7's `main.js` calls both on every render.

- [ ] **Step 1: Write `frontend/js/sidebar.js`**

```javascript
export function renderBoatList({ listEl, activeBoats, followedSlug, onBoatSelect, boatsBySlug }) {
  listEl.innerHTML = "";

  for (const boat of activeBoats) {
    const item = document.createElement("li");
    const meta = boatsBySlug ? boatsBySlug.get(boat.boatSlug) : undefined;
    const typeLabel = meta && meta.type ? ` — ${meta.type}` : "";
    item.textContent = `${boat.boatNumber}${typeLabel} (${boat.externalId})`;
    if (boat.boatSlug === followedSlug) {
      item.classList.add("following");
    }
    item.addEventListener("click", () => onBoatSelect(boat.boatSlug));
    listEl.appendChild(item);
  }

  if (activeBoats.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "Geen boten actief op deze datum.";
    empty.style.cursor = "default";
    listEl.appendChild(empty);
  }
}

export function updateDateLabel(labelEl, date) {
  labelEl.textContent = `Actief op ${date.toISOString().slice(0, 10)}`;
}
```

- [ ] **Step 2: Confirm the file has no syntax errors**

Run: `node --check frontend/js/sidebar.js`
Expected: no output (exit code 0).

- [ ] **Step 3: Commit**

```bash
git add frontend/js/sidebar.js
git commit -m "Add sidebar boat list rendering"
```

---

### Task 7: Wire it all together (`js/main.js`) and sidebar toggle

This task produces the first fully working version of the app. UI wiring — no unit tests; this
task's own manual verification (Step 3) is the real test.

**Files:**
- Create: `frontend/js/main.js`

**Interfaces:**
- Consumes: everything produced by Tasks 2–6: `fetchBoats`/`fetchRoutes` (Task 2),
  `activeBoatsOnDate`/`dateRange` (Task 3), `createMap`/`renderActiveBoats`/`renderFollowedRoute`/`clearFollowedRoute`
  (Task 4), `initTimeline` (Task 5), `renderBoatList`/`updateDateLabel` (Task 6), plus the
  `#toggle-sidebar` and `#sidebar` elements from Task 1.
- Produces: nothing consumed by a later task — this is the app's entry point, loaded directly by
  `index.html`.

- [ ] **Step 1: Write `frontend/js/main.js`**

```javascript
import { fetchBoats, fetchRoutes } from "./api.js";
import { activeBoatsOnDate, dateRange } from "./time-model.js";
import { createMap, renderActiveBoats, renderFollowedRoute, clearFollowedRoute } from "./map.js";
import { initTimeline } from "./timeline.js";
import { renderBoatList, updateDateLabel } from "./sidebar.js";

async function main() {
  const [boats, routes] = await Promise.all([fetchBoats(), fetchRoutes()]);

  const boatsBySlug = new Map(boats.map((boat) => [boat.slug, boat]));

  const routesBySlug = new Map();
  for (const patrol of routes) {
    if (!routesBySlug.has(patrol.boat_slug)) {
      routesBySlug.set(patrol.boat_slug, []);
    }
    routesBySlug.get(patrol.boat_slug).push(patrol);
  }

  const range = dateRange(routes);
  const labelEl = document.getElementById("boat-date-label");

  if (range === null) {
    labelEl.textContent = "Geen gedateerde routepunten beschikbaar.";
    return;
  }

  const mapState = createMap("map");

  const sliderEl = document.getElementById("date-slider");
  const playPauseEl = document.getElementById("play-pause");
  const dateDisplayEl = document.getElementById("date-display");
  const listEl = document.getElementById("boat-list");
  const resetButton = document.getElementById("reset-follow");
  const toggleSidebarButton = document.getElementById("toggle-sidebar");
  const sidebarEl = document.getElementById("sidebar");

  let followedSlug = null;
  let followedPatrol = null;
  let currentDate = range.min;

  function render(date) {
    currentDate = date;
    const active = activeBoatsOnDate(routes, date);
    updateDateLabel(labelEl, date);

    if (followedSlug !== null) {
      const followedBoatActive = active.find((boat) => boat.boatSlug === followedSlug);
      renderActiveBoats(mapState, [], onBoatSelect);
      renderFollowedRoute(
        mapState,
        followedPatrol,
        followedBoatActive ? { lat: followedBoatActive.lat, lng: followedBoatActive.lng } : null,
      );
    } else {
      clearFollowedRoute(mapState);
      renderActiveBoats(mapState, active, onBoatSelect);
    }

    renderBoatList({ listEl, activeBoats: active, followedSlug, onBoatSelect, boatsBySlug });
  }

  function onBoatSelect(slug) {
    followedSlug = slug;
    const boatRoutes = routesBySlug.get(slug) || [];
    followedPatrol = boatRoutes.length > 0 ? boatRoutes[0] : null;
    resetButton.hidden = false;
    render(currentDate);
  }

  resetButton.addEventListener("click", () => {
    followedSlug = null;
    followedPatrol = null;
    resetButton.hidden = true;
    clearFollowedRoute(mapState);
    render(currentDate);
  });

  toggleSidebarButton.addEventListener("click", () => {
    sidebarEl.classList.toggle("collapsed");
  });

  initTimeline({
    sliderEl,
    playPauseEl,
    dateDisplayEl,
    minDate: range.min,
    maxDate: range.max,
    onDateChange: render,
  });
}

main().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<p style="padding: 20px; color: red;">Fout bij laden: ${error.message}</p>`;
});
```

- [ ] **Step 2: Confirm the file has no syntax errors**

Run: `node --check frontend/js/main.js`
Expected: no output (exit code 0).

- [ ] **Step 3: Manually verify the full app in a browser**

Start the backend and frontend servers exactly as in Task 1 Step 6:

```bash
cd /home/scout/PycharmProjects/uboats && poetry run uvicorn app.main:app --port 8000
```

```bash
cd /home/scout/PycharmProjects/uboats/frontend && python3 -m http.server 5500
```

Open `http://localhost:5500` and check every one of the following:

1. The map loads with OpenStreetMap tiles visible (not the gray placeholder from Task 1).
2. The date display and slider are populated (not stuck at an empty/zero state) — the slider's
   range should span from the earliest to the latest dated route point in the real
   `uboats.db` data.
3. Dragging the slider updates the date display and moves boat markers on the map.
4. Clicking play (▶) auto-advances the date and markers; clicking pause (now showing ⏸) stops it;
   dragging the slider while playing also stops auto-play.
5. The sidebar lists boats active on the current date, and the list changes as the date changes.
6. Clicking a boat in the sidebar (or a marker on the map) highlights that boat's full route as a
   line, shows a distinct highlighted marker at its current interpolated position, hides other
   boats' markers, and reveals the "Terug naar volledige weergave" button.
7. Clicking that button returns to the full multi-boat view and hides the button again.
8. Clicking the `☰` button collapses/expands the sidebar.
9. No errors appear in the browser console throughout.

If a real browser is available via tooling in this environment, use it to drive these checks and
capture a screenshot of the loaded map with active boat markers visible, rather than reasoning
about the code without observing it run. Fix anything broken before proceeding — this step is the
actual test for this task and Tasks 4–6 combined.

Stop both servers once verification is complete.

- [ ] **Step 4: Commit**

```bash
git add frontend/js/main.js
git commit -m "Wire up the full app: data loading, timeline, map, sidebar, follow mode"
```

---

### Task 8: Manual end-to-end verification against the real dataset

Not a coded task — the final checkpoint confirming the whole feature works end-to-end against
genuine crawled data, mirroring how phase 1 ended.

- [ ] **Step 1: Confirm the dataset in place**

```bash
cd /home/scout/PycharmProjects/uboats
poetry run python -c "
import asyncio
from app.core.config import settings
from app.services.storage.database import create_engine, create_session_factory
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.patrol_repository import PatrolRepository

async def check():
    engine = create_engine(settings.DATABASE_URL)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        boats = await BoatRepository(session).list_summaries()
        routes = await PatrolRepository(session).list_routes()
    print(f'{len(boats)} boats, {len(routes)} patrol routes, {sum(len(r.points) for r in routes)} route points')
    await engine.dispose()

asyncio.run(check())
"
```

Expected: `10 boats, 43 patrol routes, 1067 route points` (the dataset preserved from phase 1's
verification run). If this doesn't match, something moved or changed `uboats.db` — investigate
before continuing rather than assuming the frontend is broken.

- [ ] **Step 2: Run the full app one more time end-to-end**

Repeat Task 7 Step 3's full checklist against this exact dataset, this time treating it as the
final acceptance check rather than in-progress debugging. All 9 points must pass cleanly.

- [ ] **Step 3: Run every automated test one more time**

```bash
poetry run pytest -q
node --test frontend/tests/api.test.js
node --test frontend/tests/time-model.test.js
```

Expected: `65 passed` for pytest, and both Node test files fully green (4 + 14 tests).

- [ ] **Step 4: Report back**

Summarize to the user: confirm the dataset counts, confirm the 9-point manual checklist passed,
confirm all automated tests are green, and note that the full ~1153-boat crawl (still not yet
run) will make the map meaningfully more populated whenever the user chooses to run it — nothing
in the frontend needs to change for that; it just consumes whatever is in `uboats.db`.

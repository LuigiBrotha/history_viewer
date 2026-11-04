# U-boat Route Map — Leaflet Frontend Design

## Purpose

Phase 2 of the uboat.net project: a browser-based Leaflet map with a time slider, so a user can
travel through the war and see which U-boats were on patrol on a given date, and follow one
boat's route. This is a pure consumer of the read-only API built in phase 1
(`docs/superpowers/specs/2026-08-28-uboat-scraper-design.md`) — no scraping or crawl changes.

The initial 10-boat crawl (43 patrols, 1067 route points) is real, live data already served by
the phase-1 API and is enough to build and verify this against; a full ~1153-boat crawl is not a
prerequisite.

## Decisions

| Concern | Decision |
|---|---|
| Stack | Vanilla HTML/CSS/JS + Leaflet via CDN. No build step, no npm, no framework — the app is small enough that a build pipeline would be pure overhead. |
| Location | New top-level `frontend/` directory, sibling to `app/`. Served by FastAPI through a `StaticFiles` mount at `/`, so `poetry run uvicorn app.main:app --reload` is the only process needed. |
| Data loading | Fetch `GET /api/uboats/routes` and `GET /api/uboats/boten` once on page load; everything after that (filtering by date, finding known positions) runs client-side, in memory. No pagination, no new backend endpoints — matches the phase-1 API's own stated design ("sized to be loaded once by a client and filtered/interpolated there"). Revisit only if the full-scale crawl makes the payload or client-side computation a real problem — not solved preemptively. |
| CORS | Not needed: the frontend and API share one origin, and the frontend calls the API with relative URLs. |
| "Active on date X" | A patrol is active on a date only if that date falls between its **first and last dated** route point (undated points are never used as a position, though they still render as part of the static full route line when a boat is followed). A patrol with zero dated points never appears in the date-based view. |
| Position | Only known coordinates are shown. On a date without a route point the marker stays on the last known one and its tooltip names that point's date; with several points on one date, the last one wins. Positions are never calculated. |
| Time slider | Both a draggable date slider and a play/pause auto-advance control, at a fixed default speed (e.g. 1 simulated day per 500ms) — no speed selector, no scrubber thumbnails. Range bounds are the min/max dated route point across all loaded patrols. |
| Layout | Full-screen map, collapsible sidebar listing boats active on the current date (click to follow), slider docked at the bottom of the map. |
| Follow mode | Clicking a boat (sidebar or map marker) follows the boat across patrols: the route shown is the patrol active on the selected date. Between patrols the last finished route stays without a marker, with a "niet op patrouille" message; before the first patrol only the message shows. The map fits a route when a boat is selected and when the route changes, and otherwise leaves the zoom alone. Other boats are hidden; a visible control returns to the full "all active" view. |
| Testing | The pure position/active-boat logic (`time-model.js`) gets unit tests using Node's built-in `node:test`/`assert` — no test framework, no build step, consistent with the "no build tooling" decision above. UI wiring (map rendering, slider, sidebar, click-to-follow) is verified manually in a browser, per this project's standard practice for frontend changes — there is no existing UI test harness in this repo to extend. |

## Components (`frontend/`)

- `index.html` — page shell: map container, sidebar container, slider container; loads Leaflet
  from CDN and the app's own scripts.
- `js/api.js` — fetches `/api/uboats/boten` and `/api/uboats/routes` once, returns plain data;
  no caching layer beyond "fetched once at startup" (no re-fetch, no live updates — a static
  snapshot of whatever the DB held at page load).
- `js/time-model.js` — pure functions, no DOM access: given the loaded routes and a target date,
  returns the list of `{boat, patrol, lat, lng}` currently active, using the position rule
  above. Also derives the overall min/max date range for the slider. This is the one module with
  real logic worth unit-testing in isolation.
- `js/map.js` — Leaflet map setup; renders/updates markers for the active-boats list from
  `time-model.js`, and the full polyline + highlighted marker for a followed boat.
- `js/timeline.js` — the date slider element plus play/pause controls; emits a "date changed"
  callback that `main.js` wires to a re-render.
- `js/sidebar.js` — renders the boat list for the current date from `time-model.js`'s output;
  click handler emits a "boat selected" callback.
- `js/main.js` — entry point: loads data via `api.js`, wires `timeline.js` → `time-model.js` →
  `map.js`/`sidebar.js`, wires `sidebar.js`'s selection → follow mode in `map.js`.

## Testing

- `js/time-model.js`: unit tests (Node `node:test`) covering — known position between two dated
  points; exact-match on a dated point; a patrol excluded because the target date falls outside
  its first/last dated point; a patrol excluded entirely because it has zero dated points;
  correct min/max date range derivation across multiple patrols.
- Manual, in a browser, against the real 10-boat/43-patrol dataset already in the database:
  dragging the slider shows plausible boat positions moving over time; play/pause auto-advances;
  clicking a boat in the sidebar and on the map both trigger follow mode and center the map;
  the "back to full view" control restores the multi-boat view.

## Out of scope (deferred)

- Server-side filtering/pagination for the full ~1153-boat scale — revisit only if it becomes a
  real problem after the full crawl runs.
- Attack/sinking event markers (already out of scope for the scraper itself — phase 1 never
  collects this data).
- A speed selector or scrubbing thumbnails on the time slider.
- Any backend change beyond serving the frontend and creating tables during app startup.
- Mobile/responsive layout polish — desktop-first for this iteration.

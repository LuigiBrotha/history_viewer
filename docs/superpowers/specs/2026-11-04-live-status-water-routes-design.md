# Live status, water routes and point exclusion — Design

Three phases, built and reviewed in this order. After each one the map works and can go to
`master`. Accuracy beats coverage whenever the two conflict. Domain terms are in `CONTEXT.md`.

## Phase 1: live updates and `/status`

**Goal.** Watch a crawl fill the map without reloading.

| Topic | Decision |
|---|---|
| Timestamps | `patrols.crawled_at` (last stored by the crawl) and `patrols.updated_at` (last change to anything the map shows). Both nullable; existing rows stay null until re-crawled. |
| Migration | `create_all` does not alter tables, so `init_models` adds missing columns using a `PRAGMA table_info` guard. Existing `uboats.db` files must keep working. |
| Crawl progress | One-row `crawl_progress` table holding `listing_total` (size of the full listing, before `--limit`/`--slugs`). Written at crawl start. |
| Status API | `GET /api/uboats/status` returns `listing_total`, `boats_crawled` (status `success`), `boats_failed`, `patrol_count`, `revision` (max `updated_at`, or null) and `last_patrol` (`boat_slug`, `boat_number`, `external_id`, `crawled_at`, or null). |
| Incremental API | `GET /api/uboats/routes?since=<revision>` returns patrols with `updated_at >= since`. Without `since`, it returns everything, as today. |
| Polling | Every 5 seconds, skipped while the tab is hidden. Routes are fetched only when `revision` changes, then merged by `external_id`. Refetching everything at each change would be too heavy at full scale. |
| Status line | On both pages: `47 van 1153 boten · laatste: U-99, 12 sec geleden`, plus `· 2 mislukt` when relevant. Without a total: `47 boten`. When a poll fails: `Geen verbinding, opnieuw proberen…`, keeping all data on screen. |
| Main map | Merges new data and keeps the selected date, the followed boat and the user's zoom. The slider range grows when new dates arrive. |
| `/status` page | Separate page at exactly `/status`, served by a route so that relative URLs still resolve to the root. Mobile first. Shows every patrol in a very thin line (weight 0.75), coloured on Google's Turbo ramp by departure date, linear from the start (lowest value) to the end (highest value) of the selected period, or of all history without one; a patrol departing before the period takes the lowest colour; the scale follows the data. The patrol with the newest `crawled_at` is black and on top. A draggable slider, its selection showing the whole Turbo ramp, has two handles and a draggable selection, working by mouse, touch and keyboard, and shows only patrols overlapping that period, including the black one; patrols without any date only show without a period. Fits all routes once on load and never moves on its own after that. Renders with Leaflet's canvas renderer. Tooltip: boat number, patrol and dates. Each page links to the other. |

During this phase, lines on `/status` are straight and can cross land. Phase 2 replaces them.

## Phase 2: water routes

**Goal.** Between two route points, draw the shortest route over water as a dashed line.

**Displayed geometry.** Leaflet draws a straight line in Web Mercator, so every land check tests
that line, sampled at 16 intervals, rather than a straight line in lat/lng. Routes are therefore
close to shortest, not exact great circles. Length is the sum of haversine distances.

**Land data.** Natural Earth 10m `land` and `minor_islands`, tag `v5.1.2`, gzipped in the repo, with
a data README recording the source URLs and checksums. The Kiel Canal is cut out of the land as
a 0.015° buffer around this lng/lat line: `(9.13,53.885) (9.27,54.0) (9.53,54.2) (9.68,54.30)
(9.85,54.34) (10.02,54.36) (10.15,54.368)`. No other canal counts as water.

**Algorithm**, validated in a spike on all 132 real legs whose straight line crosses land:
1. **Snap.** A point on land within 10 km of the coast moves just offshore. Beyond 10 km the leg's
   status is `on_land`.
2. **Straight check.** If the display line between the snapped points misses land, the path is
   those two points.
3. **Grid search.** Otherwise rasterize a window around the leg and label its connected water
   regions. For each endpoint, pick the nearest water cell within 10 km that belongs to the largest
   region reachable within that distance. Taking the nearest water cell without this check fails:
   Lorient snaps into an estuary pocket that is closed at grid resolution. Different regions go
   straight to the next attempt, without searching.
4. **Search.** A* with 8 neighbours, longitude cost scaled by cos(latitude), no diagonal corner
   cutting. Attempts, with `ext` the larger of the leg's lat and lng extent:

   | Attempt | Cell size (°) | Margin (°) |
   |---|---|---|
   | 1 | `clamp(ext/300, 0.005, 0.05)` | `max(0.3, ext*0.3)` |
   | 2 | `clamp(ext/600, 0.005, 0.05)` | `max(1, ext*0.8)` |
   | 3 | `clamp(ext/400, 0.01, 0.05)` | `max(4, ext*2)` |

   If all three fail the status is `no_route`.
5. **Shorten.** Pull the string: from each vertex, jump to the furthest later vertex with a clear
   display line. Interior segments may clip land by up to one grid cell, which the spike showed on
   7 of 115 routes.
6. **Endpoints.** The stored path starts and ends on the original coordinates, never snapped ones.

Spike results: 115 of 132 routed and 17 `on_land`, caused by 5 points; no `no_route`. Median 0.23 s
per leg, slowest 2.7 s, 5 s to load the land data once.

**Storage.** `water_routes`, keyed on `(from_lat, from_lng, to_lat, to_lng)`, holding `status`,
`path` (JSON) and `length_km`. Keying on coordinates means a re-crawl, which replaces route points,
keeps valid routes, duplicates are computed once, and interrupted runs resume.

**When computed.** The crawl computes a patrol's legs before storing the patrol, so a patrol
appears with its lines ready. A routing failure is logged and never fails the crawl. A separate
`python -m app.compute_water_routes [--force]` fills in existing data, bumping `updated_at` per
patrol. The API process never loads land data in this phase.

**Leg status**, derived when reading, so that changing the threshold needs no recalculation:

| Status | Rule | Display |
|---|---|---|
| `ok` | routed and not too fast | blue dashed line |
| `suspect` | both dates known and `length_km > 815 * max(1, days)` | orange dashed line (`#e67e00`), tooltip with km and days |
| `on_land` | stored status | no line; `?` label at the midpoint: `Route onzeker: punt ligt op land` |
| `no_route` | stored status | no line; `?` label: `Route onzeker: geen waterroute gevonden` |
| `not_computed` | no stored row | no line, no label |

815 km per day is 18.3 knots over 24 hours, the IXC surface speed on uboat.net. Dates have no time,
so consecutive dates can span up to nearly 2 days: this rule deliberately flags extreme jumps
rather than proving them impossible. The `?` marks the leg and never implies a position.

**API.** Each patrol in `/api/uboats/routes` gains `legs`: `from_sequence`, `to_sequence`, `status`,
`reason`, `path`, `length_km`, `days`.

**Display.** The followed route and the overview tail draw legs by the table above. The followed
boat's route points show as small dots. A tail with an uncertain leg has no line and no label; the
marker tooltip adds `route onzeker`. On `/status` all drawn legs are dashed, in the patrol's colour;
suspect legs are not orange there, and uncertain legs have no label.

## Phase 3: excluding a point

**Goal.** Remove an unreliable point from a route, reversibly.

| Topic | Decision |
|---|---|
| Storage | `excluded_route_points`, keyed on `(external_id, lat, lng, occurrence)`, where `occurrence` is the 0-based ordinal, by sequence, among the patrol's rows with those coordinates. Keyed by position rather than sequence or date, so exclusions survive a re-crawl, including one that changes a stored date to NULL or shifts sequences. An exclusion hides only the clicked row, never a twin elsewhere on the route (a home port is often both first and last); the last-point check counts visible rows. Source data stays untouched. |
| API | `POST /api/uboats/routes/{external_id}/excluded-points` and `DELETE` on the same path, both with JSON body `{"sequence": n}`. Both return the updated patrol and bump `updated_at`. 404 for an unknown patrol or sequence. 409 when excluding would leave no point. |
| Reading | `points` and `legs` skip excluded points, so markers, timeline and tails simply follow. Excluded points are listed in `excluded_points`. |
| New leg | Excluding B from A-B-C computes A-C immediately on a worker thread, loading land data lazily on first use (about 5 s). If routing fails the exclusion still succeeds and the leg is `not_computed`. |
| UI | Click a dot of the followed route for a popup with `Punt uitsluiten`. The sidebar lists `Uitgesloten punten` for the shown patrol, each with `Herstellen`. No confirmation dialog, because it is reversible. |
| Network | The app may run on the local network (`--host 0.0.0.0`) to be viewed from a phone, without a login, and is read-only there. `POST` and `DELETE` on excluded points return 403 unless the client address is loopback (`127.0.0.1` or `::1`). `GET /api/uboats/status` gains `can_edit`, true only for a loopback client, and the UI hides `Punt uitsluiten`, `Herstellen` when it is false, while still listing excluded points. `python -m app.main` binds to `127.0.0.1` by default. |

## Phase 4: ships hit by U-boats

**Goal.** See on the map which ships were sunk, damaged or captured, with their tonnage.

**Source.** `uboat.net/boats/successes/{slug}.html` lists date, commander, ship name, tons,
nationality and convoy, with `(d.)` for damaged and `(c.)` for captured. Each row links to
`/allies/merchants/ship/{id}.html`, the only place with a position, for example
`Position 50° 31'N, 11° 05'W - Grid BF 1144`. Coordinates are not in the successes page, so every
ship costs one request. The site says some positions are unknown.

| Topic | Decision |
|---|---|
| Storage | `ship_hits`, unique on `(ship_external_id, boat_slug, date)`, holding name, tons, nationality, convoy, `outcome` (`sunk`, `damaged`, `captured`), nullable `lat`/`lng`, `position_checked` and `updated_at`. One ship can be hit more than once. |
| Crawling | Separate `python -m app.crawl_ships [--limit N] [--slugs ...] [--force] [--delay N]`, with the same courtesy as the main crawl: 10 s between requests, one at a time. Resumes per ship, so stopping loses at most one ship. A ship with no position is not retried without `--force`. |
| API | `GET /api/uboats/ships?since=<revision>` with the same semantics as routes. `revision` in the status endpoint also covers `ship_hits`. |
| Main map | A ship appears on its date and stays. Followed boat: only that boat's ships. Tooltip: `Magog — 2.053 ton — gezonken door U-99 op 1940-07-05`. |
| `/status` | Shows all ships up to now, regardless of date, since the page has no timeline. |
| Symbols | Sunk: filled dark circle (`#222222`). Damaged: hollow dark circle. Captured: filled purple circle (`#7a3db8`). |
| Totals | In the sidebar, up to the selected date: `87 gezonken (412.000 ton) · 5 beschadigd (37.965 ton) · 1 buitgemaakt (4.000 ton)`, with parts at zero left out. The followed boat's total covers only that boat. |
| Unknown position | Never plotted and never estimated. Counted in totals, and followed boats list them in the sidebar as `positie onbekend`. |
| Ship details | The same request that gives the position also gives the facts on the ship's page (type, completion, owner, homeport, nationality, fate, complement, convoy, route, cargo, history, notes on the event). They go in `ship_details`, one row per ship. A hit is pending when its position is unchecked or its ship has no details row, so earlier crawls fill in details on the next run; a ship hit twice is fetched once per run. |
| Ship panel | `GET /api/uboats/ships/{id}` returns the details and every hit of that ship (404 when none). Clicking a ship marker opens the boat panel with the hit's own facts at once, then the details, the notes under `Wat er gebeurde` and other hits under `Ook getroffen`. A button opens the panel of the boat that hit it, without changing the followed boat. Ships in a boat's panel are buttons that open the ship. |

Validation: parsing the U-99 page must reproduce the site's own figures, 39 ships sunk for 246,794
tons and 5 damaged for 37,965 tons, 284,759 in all.

## Historical map layer

Both maps show the "Ww2 allied axis" world maps from Wikimedia Commons (CC BY-SA 3.0) as a
half-transparent layer in soft tints, above the base map and below the routes. A map counts
from the first of its month. The timeline shows the last map on or before the selected date;
`/status` the last on or before the end of the selection. Before the first map there is none.
The sources are in Robinson without georeferencing: `tools/build_atlas_overlays.py` holds a
position fit (overlap with Natural Earth land 0.91) and produces Web Mercator images.

## Heatmap

`/heatmap` has the same period slider, live updates, historical layer and mobile-first header as
`/status`. It counts how many patrols overlapping the period pass through each 0.5° cell along
their drawn water routes, once per patrol per cell. Colours are Turbo on a square-root scale of
the selection's 99th percentile, so that bases do not wash out the ocean, transparent where nothing passed. Patrols without a water route
do not count. Ships hit by U-boats are not included.

## Out of scope

- Periodically checking uboat.net for changes.
- WebSockets or server-sent events: the crawl is a separate process and 5-second polling suffices.
- Offline maps.
- Canals other than the Kiel Canal.
- Editing or adding coordinates.

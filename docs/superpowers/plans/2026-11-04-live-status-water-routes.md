# Live Status, Water Routes and Point Exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the map update live during a crawl, add a `/status` map of all routes, draw water routes between route points, let the user exclude unreliable points, and show ships hit by U-boats with their tonnage.

**Architecture:** The crawl stays a separate process that writes to SQLite; pages poll a small status endpoint and fetch changed patrols incrementally. Water routes are computed by a pure routing package and stored by coordinate pair, and leg status is derived when reading. Exclusions live in their own table, so source data stays untouched. Ship hits come from a separate resumable crawl and reuse the same polling.

**Tech Stack:** FastAPI + wireup class-based handlers, SQLAlchemy async on SQLite, vanilla ES modules + Leaflet 1.9.4, `node:test`, pytest. New in Phase 2: shapely, numpy, scipy.

**Spec:** `docs/superpowers/specs/2026-11-04-live-status-water-routes-design.md`

## Global Constraints

- Build phases in order, each on its own branch. Stop after each phase for the user's browser check; merge to `master` only after their approval.
- No build step or npm install in `frontend/`. Frontend logic that can be pure gets `node:test` tests.
- All new handlers follow `app/http/api/uboats/routes.py`: module-level class `RequestHandler` with its own `APIRouter(route_class=WireupRoute)`, discovered automatically.
- A mount at `/` catches everything, so it stays in the lifespan, after Wireup registers handlers.
- User-facing text is Dutch and copied exactly from the spec. Never display a calculated position.
- Keep `poetry run uvicorn app.main:app --reload` working with an existing `uboats.db`.

Run tests with `poetry run pytest -q` and `cd frontend && node --test tests/`.

## Review Focus

1. Browser polls while the crawl is committing: the API must not fail with `database is locked`, and a failed poll must keep the data on screen. (Task 2, Task 3)
2. Data refresh while following a boat: new patrol objects must not re-zoom the map or lose the followed boat and date. (Task 4)
3. Empty database or no crawl yet: `/status` and the status line render instead of an error. (Task 1, Task 5)
4. Re-crawl of a patrol: water routes and exclusions must survive `upsert_patrol` replacing its points. (Task 7, Task 10)
5. An existing `uboats.db` without the new columns and tables must start cleanly and keep its data. (Task 1)

---

# Phase 1: Live updates and `/status`

### Task 1: Timestamps, migration and status API

**Files:**
- Modify: `app/services/storage/models.py`, `app/services/storage/database.py`, `app/services/storage/patrol_repository.py`, `app/services/export/uboats.py`
- Create: `app/services/storage/crawl_status_repository.py`, `app/http/api/uboats/status.py`
- Test: `tests/services/storage/test_database.py`, `tests/services/storage/test_crawl_status_repository.py`, `tests/services/storage/test_patrol_repository.py`, `tests/http/api/test_status.py`

**Interfaces:**
- Produces: `Patrol.crawled_at`, `Patrol.updated_at` (`UTCDateTime | None`); model `CrawlProgress(id=1, listing_total: int)`
- Produces: `CrawlStatusRepository(session)` with `set_listing_total(total: int) -> None` and `get_status() -> CrawlStatusOut`
- Produces: dataclasses `LastPatrolOut(boat_slug, boat_number, external_id, crawled_at)` and `CrawlStatusOut(listing_total: int | None, boats_crawled: int, boats_failed: int, patrol_count: int, revision: datetime | None, last_patrol: LastPatrolOut | None)`
- Produces: `GET /api/uboats/status` returning `CrawlStatusOut`

- [ ] **Step 1: Write the failing tests**

```python
async def test_init_models_adds_missing_patrol_columns_to_an_existing_database(tmp_path):
    # create a patrols table with the old columns and one row via raw SQL, then:
    await init_models(engine)
    # assert crawled_at and updated_at exist, and the row survived with both NULL

async def test_upsert_patrol_sets_crawled_at_and_updated_at(tmp_path): ...

async def test_get_status_on_an_empty_database(tmp_path):
    status = await CrawlStatusRepository(session).get_status()
    assert status == CrawlStatusOut(None, 0, 0, 0, None, None)

async def test_get_status_reports_the_newest_crawled_patrol(tmp_path):
    # two patrols stored in order; one legacy patrol with NULL timestamps
    assert status.last_patrol.external_id == "second"
    assert status.revision == status.last_patrol.crawled_at
    assert status.patrol_count == 3

async def test_get_status_counts_success_and_failure_separately(tmp_path): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/services/storage tests/http/api/test_status.py -q`
Expected: FAIL on missing columns, repository and handler.

- [ ] **Step 3: Implement**

In `init_models`, after `create_all`, read `PRAGMA table_info(patrols)` and run `ALTER TABLE patrols ADD COLUMN ...` for each missing column. `upsert_patrol` sets both timestamps to one `datetime.now(timezone.utc)` in insert and update.

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add crawl timestamps and a status endpoint"
```

### Task 2: Incremental routes and crawl progress

**Files:**
- Modify: `app/services/storage/patrol_repository.py`, `app/http/api/uboats/routes.py`, `app/crawl.py`
- Test: `tests/services/storage/test_patrol_repository.py`, `tests/http/api/test_routes.py`, `tests/test_crawl.py`

**Interfaces:**
- Consumes: `CrawlStatusRepository.set_listing_total`, `Patrol.updated_at`
- Produces: `PatrolRepository.list_routes(since: datetime | None = None)`; `GET /api/uboats/routes?since=<iso datetime>`

- [ ] **Step 1: Write the failing tests**

```python
async def test_list_routes_since_returns_only_changed_patrols(tmp_path):
    # older patrol, cursor, newer patrol
    assert [r.external_id for r in await repo.list_routes(since=cursor)] == ["newer"]

async def test_list_routes_since_includes_a_patrol_exactly_at_the_cursor(tmp_path): ...

async def test_list_routes_since_excludes_patrols_without_a_timestamp(tmp_path): ...

async def test_status_reads_while_another_connection_is_writing(tmp_path):
    # hold a write transaction for 0.2 s on one connection; get_status on another
    # connection must return rather than raise OperationalError

async def test_main_records_the_full_listing_size_before_limit_is_applied(tmp_path, monkeypatch): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/services/storage/test_patrol_repository.py tests/http/api/test_routes.py tests/test_crawl.py -q`
Expected: FAIL on the unknown `since` argument and the missing listing total.

- [ ] **Step 3: Implement**

The filter is `Patrol.updated_at >= since`. Add an optional `since: datetime | None = None` query parameter to the handler. In `crawl.main`, call `set_listing_total(len(boat_refs))` straight after `fetch_listing`, before the `--slugs` filter. If the lock test fails, set a SQLite busy timeout in `create_engine`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add incremental route fetching and record the crawl total"
```

### Task 3: Live data module

**Files:**
- Create: `frontend/js/live.js`
- Modify: `frontend/js/api.js`
- Test: `frontend/tests/live.test.js`, `frontend/tests/api.test.js`

**Interfaces:**
- Produces in `api.js`: `fetchStatus()`, `fetchRoutes(since = null)`
- Produces in `live.js`: `mergeRoutes(routes, changed) -> routes`, replacing by `external_id` and otherwise keeping order; `statusLine(status, now: Date) -> string`; `startPolling({ intervalMs, fetchStatus, fetchRoutes, isHidden, onData, onStatus, onError, setTimer }) -> { stop }`

- [ ] **Step 1: Write the failing tests**

```js
test("mergeRoutes replaces a patrol by external_id and appends new ones", ...);
test("statusLine shows progress and the last boat", () => {
  assert.equal(statusLine(status, now), "47 van 1153 boten · laatste: U-99, 12 sec geleden");
});
test("statusLine adds failures only when there are any", ...); // "· 2 mislukt"
test("statusLine without a total", ...);                       // "47 boten"
test("statusLine with no last patrol", ...);                   // "0 boten"
test("poll does not fetch routes when the revision is unchanged", ...);
test("poll fetches routes since the previous revision when it changes", ...);
test("poll with a null previous revision fetches all routes", ...);
test("poll skips the request while the tab is hidden", ...);
test("poll reports an error, keeps polling and does not call onData", ...);
test("fetchRoutes adds an encoded since parameter", ...);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test tests/`
Expected: FAIL because `live.js` does not exist.

- [ ] **Step 3: Implement `frontend/js/live.js` and extend `api.js`**

Poll with an injected timer so tests need no real waiting. Update the stored revision only after routes were fetched successfully, so a failed fetch retries.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test tests/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "Add polling and merge logic for live data"
```

### Task 4: Live main map

**Files:**
- Modify: `frontend/js/main.js`, `frontend/js/map.js`, `frontend/js/timeline.js`, `frontend/js/time-model.js`, `frontend/index.html`, `frontend/css/style.css`
- Test: `frontend/tests/time-model.test.js`, `frontend/tests/timeline.test.js`

**Interfaces:**
- Consumes: `startPolling`, `mergeRoutes`, `statusLine`
- Produces: `sliderValueForDate(minDate: Date, date: Date) -> number` in `timeline.js`; `initTimeline(...)` also returns `setRange(minDate, maxDate)`; `shouldFitRoute(fittedExternalId, patrol) -> boolean` in `time-model.js`

- [ ] **Step 1: Write the failing tests**

```js
test("sliderValueForDate keeps the same date after the range starts earlier", ...);
test("shouldFitRoute is false for a new object of the same patrol", () => {
  assert.equal(shouldFitRoute("patrol_1", { external_id: "patrol_1" }), false);
});
test("shouldFitRoute is true for another patrol", ...);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test tests/`
Expected: FAIL on missing exports.

- [ ] **Step 3: Implement**

Keep `routes` and `routesBySlug` in mutable state that a refresh rebuilds, then call `setRange` and `render(currentDate)`. `mapState.fittedPatrol` becomes `fittedExternalId`. Put the status line in a new `#live-status` element in the sidebar, with a link to `/status`. The page must load with an empty database: start polling before the existing "no dated points" return, and create the map on first data.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test tests/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "Update the main map live while keeping date, zoom and followed boat"
```

### Task 5: `/status` page

**Files:**
- Create: `app/http/status_page.py`, `frontend/status.html`, `frontend/js/status.js`, `frontend/js/status-map.js`
- Modify: `app/main.py` (share `FRONTEND_DIR` through `app/core/config.py` or a small constant module), `tests/test_main.py`, `frontend/css/style.css`
- Test: `tests/test_main.py`, `frontend/tests/status-map.test.js`

**Interfaces:**
- Consumes: `fetchStatus`, `fetchRoutes`, `startPolling`, `mergeRoutes`, `statusLine`
- Produces: `routeColor(patrol, lastExternalId) -> "#cc3300" | "#0077cc"`, `routeLatLngs(patrol) -> [[lat, lng], ...]`

- [ ] **Step 1: Write the failing tests**

```python
def test_reload_server_serves_the_status_map_without_a_redirect(reload_server):
    response = requests.get(f"{reload_server}/status", timeout=5, allow_redirects=False)
    assert response.status_code == 200
    assert '<div id="status-map">' in response.text
```

```js
test("routeColor is red only for the last crawled patrol", ...);
test("routeColor is blue for every patrol when nothing has been crawled yet", ...);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_main.py -q` and `cd frontend && node --test tests/`
Expected: `/status` returns 404, and `status-map.js` is missing.

- [ ] **Step 3: Implement**

The handler returns `FileResponse(FRONTEND_DIR / "status.html")` from `GET /status` with `include_in_schema=False`. Keep a `Map` of `external_id` to polyline and update only what changed; the previous red route goes blue and the new one goes red with `bringToFront()`. Create the map with `preferCanvas: true`, and call `fitBounds` once.

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest -q` and `cd frontend && node --test tests/`
Expected: all pass.

- [ ] **Step 5: Verify live behaviour in a real browser**

With the server running, run a real small crawl in a second terminal: `poetry run python -m app.crawl --slugs u99 --force`. In headless Firefox, confirm on `/status` and `/` that the route appears without reload, that it is red, that the status line changes, and that a followed boat and zoom are kept on `/`. Stop the server mid-way once and confirm that `Geen verbinding, opnieuw proberen…` appears and that data stays visible.

- [ ] **Step 6: Update the README and commit**

```bash
git add app frontend tests README.md
git commit -m "Add a live status map of all routes"
```

- [ ] **Step 7: Phase gate**

Ask the user to check the map during a crawl. Merge to `master` only after their approval.

---

# Phase 2: Water routes

### Task 6: Routing package

**Files:**
- Create: `app/services/routing/__init__.py`, `app/services/routing/land.py`, `app/services/routing/water_router.py`, `app/services/routing/data/README.md`, `app/services/routing/data/ne_10m_land.geojson.gz`, `app/services/routing/data/ne_10m_minor_islands.geojson.gz`
- Modify: `pyproject.toml`
- Test: `tests/services/routing/__init__.py`, `tests/services/routing/test_water_router.py`

**Interfaces:**
- Produces: `load_land() -> Land` (cached with `lru_cache`)
- Produces: `RoutedLeg(status: Literal["ok", "on_land", "no_route"], path: list[tuple[float, float]] | None, length_km: float | None)`
- Produces: `route_leg(start: tuple[float, float], end: tuple[float, float], land: Land | None = None) -> RoutedLeg`, with points as `(lat, lng)`

- [ ] **Step 1: Add dependencies and data**

Run `poetry add shapely numpy scipy`. Download both files from `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/`, gzip them, and record URLs and SHA-256 values in the data README.

- [ ] **Step 2: Write the failing tests against the real land data**

```python
def test_open_sea_leg_is_a_straight_two_point_path(): ...   # (50.0, -20.0) to (52.0, -25.0)

def test_path_starts_and_ends_on_the_original_coordinates():
    leg = route_leg(LORIENT, BAY_OF_BISCAY)
    assert leg.path[0] == LORIENT and leg.path[-1] == BAY_OF_BISCAY

def test_lorient_reaches_open_sea():                        # regression from the spike
    assert route_leg((47.85, -3.25), (46.95, -9.25)).status == "ok"

def test_kiel_to_brunsbuettel_uses_the_canal():
    leg = route_leg((54.3667, 10.1667), (53.9, 9.1333))
    assert leg.status == "ok" and leg.length_km < 150       # around Denmark is over 1000 km

def test_kiel_to_bergen_stays_off_jutland(): ...            # (54.3667, 10.1667) to (61.35, 3.8667), 900 < km < 1200

def test_point_deep_inland_is_on_land():
    assert route_leg((76.65, -26.5), (74.85, 15.5)).status == "on_land"

def test_point_just_inland_is_snapped_and_routed(): ...     # (47.85, -3.25), 7.4 km inland

def test_interior_segments_stay_within_one_cell_of_water(): ...

def test_landlocked_water_has_no_route():
    assert route_leg(CASPIAN_SEA, NORTH_SEA).status == "no_route"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `poetry run pytest tests/services/routing -q`
Expected: FAIL because the module does not exist.

- [ ] **Step 4: Implement the algorithm from the spec's Phase 2 section**

Use `shapely.contains_xy` to rasterize and `scipy.ndimage.label` with 4-connectivity for regions. The A* heuristic uses the cosine at the window's highest absolute latitude, which keeps it admissible. Clamp latitude to ±85.

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/services/routing -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/routing tests/services/routing pyproject.toml
git commit -m "Add shortest water route calculation"
```

### Task 7: Stored routes and leg status

**Files:**
- Create: `app/services/storage/water_route_repository.py`, `app/services/routing/legs.py`
- Modify: `app/services/storage/models.py`, `app/services/storage/patrol_repository.py`, `app/services/export/uboats.py`
- Test: `tests/services/storage/test_water_route_repository.py`, `tests/services/routing/test_legs.py`, `tests/services/storage/test_patrol_repository.py`

**Interfaces:**
- Consumes: `RoutedLeg`
- Produces: `WaterRoute` model; `WaterRouteRepository.save(start, end, leg)`, `get_many(pairs) -> dict[pair, RoutedLeg]` (chunked to stay under SQLite's parameter limit), `missing(pairs, force=False) -> list[pair]`
- Produces: `build_legs(points: list[RoutePointOut], routes: dict) -> list[LegOut]`
- Produces: `LegOut(from_sequence, to_sequence, status, reason, path, length_km, days)`; `PatrolRouteOut.legs`
- Produces: constant `MAX_KM_PER_DAY = 815`

- [ ] **Step 1: Write the failing tests**

```python
def test_ok_leg_at_exactly_the_limit_is_not_suspect(): ...      # 815 km, 1 day
def test_leg_over_the_limit_is_suspect(): ...                   # 816 km, 1 day
def test_same_date_uses_a_minimum_of_one_day(): ...             # 816 km, 0 days -> suspect
def test_limit_scales_with_days(): ...                          # 1600 km, 2 days -> ok
def test_undated_point_is_never_suspect(): ...
def test_on_land_leg_has_the_dutch_reason():
    assert leg.reason == "Route onzeker: punt ligt op land"
def test_no_route_leg_has_the_dutch_reason():
    assert leg.reason == "Route onzeker: geen waterroute gevonden"
def test_missing_stored_route_is_not_computed(): ...

async def test_water_routes_survive_a_recrawl_of_the_patrol(tmp_path):
    # upsert, save a route, upsert the same patrol again
    assert (await repo.list_routes())[0].legs[0].status == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/services/routing/test_legs.py tests/services/storage -q`
Expected: FAIL on missing modules.

- [ ] **Step 3: Implement, with `list_routes` attaching `legs` to each patrol**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add app tests
git commit -m "Store water routes and derive leg status"
```

### Task 8: Compute during the crawl, plus a backfill command

**Files:**
- Create: `app/compute_water_routes.py`
- Modify: `app/crawl.py`, `app/services/storage/patrol_repository.py`, `README.md`
- Test: `tests/test_compute_water_routes.py`, `tests/test_crawl.py`

**Interfaces:**
- Consumes: `route_leg`, `WaterRouteRepository`
- Produces: `compute_routes_for_points(points, session_factory, route_leg, force=False) -> None`; `PatrolRepository.touch(external_id)`; `crawl_boats(..., route_leg=None)`

- [ ] **Step 1: Write the failing tests**

```python
async def test_crawl_stores_routes_before_the_patrol_appears(tmp_path): ...
async def test_routing_failure_does_not_fail_the_crawl(tmp_path): ...
async def test_backfill_skips_stored_pairs_unless_forced(tmp_path): ...
async def test_backfill_bumps_updated_at_but_not_crawled_at(tmp_path): ...
async def test_backfill_continues_after_a_failing_leg(tmp_path): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/test_compute_water_routes.py tests/test_crawl.py -q`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement**

Run routing via `asyncio.to_thread`. Mirror the shape of `app/crawl.py`, including its printed progress. Document the command in the README.

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 5: Backfill the real data**

Run: `poetry run python -m app.compute_water_routes`
Expected: about 1024 legs processed. Confirm on the database that 5 unique coordinates account for the `on_land` legs, and report the number of suspect legs. Compare with the spec's spike numbers and explain any difference.

- [ ] **Step 6: Commit**

```bash
git add app tests README.md
git commit -m "Compute water routes during the crawl and add a backfill command"
```

### Task 9: Draw legs on both maps

**Files:**
- Modify: `frontend/js/map.js`, `frontend/js/status-map.js`, `frontend/js/time-model.js`, `frontend/js/main.js`, `frontend/css/style.css`
- Test: `frontend/tests/time-model.test.js`, `frontend/tests/status-map.test.js`

**Interfaces:**
- Consumes: `legs` from the API
- Produces: `legStyle(status) -> { color, dashArray } | null`; `legMidpoint(leg, patrol) -> [lat, lng] | null`; `tailLeg(patrol, position) -> leg | null`; `statusLegStyle(status, color) -> { color, dashArray } | null`; `knownPosition` also returns `sequence`

- [ ] **Step 1: Write the failing tests**

```js
test("legStyle is dashed blue for ok and dashed orange for suspect", ...);   // #0077cc, #e67e00
test("legStyle is null for on_land, no_route and not_computed", ...);
test("statusLegStyle ignores suspect and keeps the page colour", ...);
test("tailLeg finds the leg ending at the current position", ...);
test("tailLeg returns null on the patrol's first point", ...);
test("legMidpoint uses the two route points, for an uncertain leg", ...);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test tests/`
Expected: FAIL on missing exports.

- [ ] **Step 3: Implement**

Remove the straight lines from `lastLeg` and from `renderFollowedRoute`. Fit bounds on all route points and paths. Followed route: route point dots, suspect tooltip with km and days, `?` divIcon with the reason at each uncertain leg. Overview tail: draw only `tailLeg`, and add `route onzeker` to the tooltip when its status is uncertain.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test tests/`
Expected: all pass.

- [ ] **Step 5: Verify in a real browser**

Screenshot U-101 and U-143. Confirm dashed lines around land, the Kiel Canal in use, orange legs, `?` labels, and markers exactly on the route points. Update `CONTEXT.md` with **Verdacht traject**.

- [ ] **Step 6: Commit and phase gate**

```bash
git add frontend CONTEXT.md
git commit -m "Draw water routes as dashed lines on both maps"
```

Ask the user to check the routes. Merge to `master` only after their approval.

---

# Phase 3: Excluding a point

### Task 10: Exclusion storage and reading

**Files:**
- Modify: `app/services/storage/models.py`, `app/services/storage/patrol_repository.py`, `app/services/export/uboats.py`, `app/services/routing/legs.py`
- Test: `tests/services/storage/test_patrol_repository.py`

**Interfaces:**
- Consumes: `build_legs`
- Produces: `ExcludedRoutePoint` model; `PatrolRepository.exclude_point(external_id, sequence) -> tuple[lat, lng]`, `restore_point(external_id, sequence)`, raising `PatrolNotFound`, `PointNotFound`, `LastPointError`; `PatrolRouteOut.excluded_points: list[RoutePointOut]`

- [ ] **Step 1: Write the failing tests**

```python
async def test_excluded_point_leaves_points_and_joins_excluded_points(tmp_path): ...
async def test_legs_connect_the_neighbours_of_an_excluded_point(tmp_path): ...
async def test_exclusion_survives_a_recrawl_with_new_sequences(tmp_path): ...
async def test_undated_point_can_be_excluded_and_restored(tmp_path): ...
async def test_excluding_the_only_remaining_point_is_refused(tmp_path): ...
async def test_exclude_and_restore_bump_updated_at(tmp_path): ...
async def test_source_route_point_row_is_untouched(tmp_path): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/services/storage/test_patrol_repository.py -q`
Expected: FAIL on missing methods.

- [ ] **Step 3: Implement**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add app tests
git commit -m "Store reversible exclusions of route points"
```

### Task 11: Exclusion API

**Files:**
- Create: `app/http/api/uboats/excluded_points.py`
- Modify: `app/main.py`
- Test: `tests/http/api/test_excluded_points.py`

**Interfaces:**
- Consumes: `exclude_point`, `restore_point`, `route_leg`, `compute_routes_for_points`
- Produces: `POST` and `DELETE /api/uboats/routes/{external_id}/excluded-points` with body `{"sequence": n}`, returning `PatrolRouteOut`

- [ ] **Step 1: Write the failing tests**

```python
async def test_excluding_a_point_computes_the_new_leg(tmp_path): ...
async def test_exclusion_succeeds_when_routing_fails(tmp_path):
    # new leg status is "not_computed"
async def test_unknown_patrol_returns_404(tmp_path): ...
async def test_unknown_sequence_returns_404(tmp_path): ...
async def test_excluding_the_last_point_returns_409(tmp_path): ...
async def test_restoring_returns_the_point_to_the_route(tmp_path): ...
def test_main_binds_to_loopback(): ...   # uvicorn.run host in app/main.py is 127.0.0.1
async def test_excluding_from_a_network_client_returns_403(tmp_path): ...    # client host 192.168.2.20
async def test_restoring_from_a_network_client_returns_403(tmp_path): ...
async def test_loopback_clients_may_edit_including_ipv6(tmp_path): ...       # 127.0.0.1 and ::1
async def test_status_reports_can_edit_only_for_a_loopback_client(tmp_path): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/http/api/test_excluded_points.py -q`
Expected: FAIL because the handler does not exist.

- [ ] **Step 3: Implement**

Route through `asyncio.to_thread`, so the 5-second land load never blocks other requests. Restoring also computes any legs that are missing. Check `request.client.host` before doing anything, and add `can_edit` to the status response from the same check. Document the network command, `poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001`, in the README, including that it is read-only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add an API to exclude and restore route points"
```

### Task 12: Exclusion UI

**Files:**
- Modify: `frontend/js/api.js`, `frontend/js/map.js`, `frontend/js/sidebar.js`, `frontend/js/main.js`, `frontend/index.html`, `frontend/css/style.css`, `README.md`, `CONTEXT.md`
- Test: `frontend/tests/api.test.js`

**Interfaces:**
- Consumes: the exclusion API, `mergeRoutes`
- Produces: `excludePoint(externalId, sequence)`, `restorePoint(externalId, sequence)`, `canEdit(status) -> boolean`; `renderExcludedPoints({ listEl, patrol, onRestore })`, with `onRestore` null when editing is not allowed

- [ ] **Step 1: Write the failing tests**

```js
test("excludePoint posts the sequence as JSON and returns the patrol", ...);
test("restorePoint sends DELETE with the sequence as JSON", ...);
test("excludePoint rejects with a message on a 409", ...);
test("canEdit is false unless the status says so", ...);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test tests/`
Expected: FAIL on missing exports.

- [ ] **Step 3: Implement**

Clicking a followed route dot opens a popup with `Punt uitsluiten`. When `status.can_edit` is false, show no popup button and no `Herstellen`, but keep listing excluded points. Merge the returned patrol with `mergeRoutes` and render without moving the map; keep the button disabled while a request runs, since the first can take about 5 seconds. Show API errors in `#follow-status`. Add **Uitgesloten punt** to `CONTEXT.md`, and describe the feature in the README.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test tests/`
Expected: all pass.

- [ ] **Step 5: Verify in a real browser**

Follow U-101 and exclude a point at an orange leg. Confirm the new leg appears, the zoom stays, `/status` follows within 5 seconds, a reload keeps the exclusion, and `Herstellen` brings the point back. Then run `poetry run python -m app.crawl --slugs u101 --force` and confirm a new exclusion survives it.

- [ ] **Step 6: Commit and phase gate**

```bash
git add frontend README.md CONTEXT.md
git commit -m "Add excluding and restoring route points to the map"
```

Ask the user to check the flow. Merge to `master` only after their approval.

---

# Phase 4: Ships hit by U-boats

### Task 13: Parsers for ship hits

**Files:**
- Create: `app/services/scraping/uboat_net/successes.py`, `app/services/scraping/uboat_net/ship.py`, `tests/fixtures/uboat_net/successes_u99.html`, `tests/fixtures/uboat_net/ship_408.html`
- Modify: `app/services/scraping/uboat_net/types.py`
- Test: `tests/services/scraping/uboat_net/test_successes.py`, `tests/services/scraping/uboat_net/test_ship.py`

**Interfaces:**
- Produces: `ShipHitRef(ship_external_id: str, boat_slug: str, name: str, date: date, tons: int, nationality: str | None, convoy: str | None, outcome: Literal["sunk", "damaged", "captured"], detail_url: str)`
- Produces: `parse_successes(html: str, slug: str) -> list[ShipHitRef]`, `fetch_successes(client, slug) -> list[ShipHitRef]`
- Produces: `parse_ship_position(html: str) -> tuple[float, float] | None`, `fetch_ship_position(client, detail_url) -> tuple[float, float] | None`

- [ ] **Step 1: Save fixtures**

Fetch `https://uboat.net/boats/successes/u99.html` and `https://uboat.net/allies/merchants/ship/408.html` with `PoliteHttpClient`. Also find and save a ship page without a position, and one with several attacks if the U-99 list has one.

- [ ] **Step 2: Write the failing tests**

```python
def test_u99_reproduces_the_sites_own_totals():
    hits = parse_successes(FIXTURE, "u99")
    sunk = [h for h in hits if h.outcome in ("sunk", "captured")]
    damaged = [h for h in hits if h.outcome == "damaged"]
    assert (len(sunk), sum(h.tons for h in sunk)) == (39, 246794)
    assert (len(damaged), sum(h.tons for h in damaged)) == (5, 37965)

def test_first_hit_is_magog():
    assert parse_successes(FIXTURE, "u99")[0] == ShipHitRef(
        "408", "u99", "Magog", date(1940, 7, 5), 2053, "ca", "HX-52", "sunk",
        "https://uboat.net/allies/merchants/ship/408.html",
    )

def test_boat_without_successes_returns_nothing(): ...

def test_position_converts_degrees_and_minutes_with_west_negative():
    lat, lng = parse_ship_position(SHIP_408)
    assert (round(lat, 4), round(lng, 4)) == (50.5167, -11.0833)

def test_page_without_a_position_returns_none(): ...
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_successes.py tests/services/scraping/uboat_net/test_ship.py -q`
Expected: FAIL because the modules do not exist.

- [ ] **Step 4: Implement with selectolax, following `patrol_list.py`**

The site's legend counts captured ships in the sunk total, which is why the first test groups them. Check how `(d.)` and `(c.)` appear in the fixture's markup rather than assuming.

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/services/scraping -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add app tests
git commit -m "Parse ship hits and their positions from uboat.net"
```

### Task 14: Storage, crawl command and API

**Files:**
- Create: `app/services/storage/ship_hit_repository.py`, `app/crawl_ships.py`, `app/http/api/uboats/ships.py`
- Modify: `app/services/storage/models.py`, `app/services/export/uboats.py`, `app/services/storage/crawl_status_repository.py`, `README.md`
- Test: `tests/services/storage/test_ship_hit_repository.py`, `tests/test_crawl_ships.py`, `tests/http/api/test_ships.py`

**Interfaces:**
- Consumes: `ShipHitRef`, `fetch_successes`, `fetch_ship_position`
- Produces: `ShipHit` model; `ShipHitRepository.upsert_refs(refs)`, `pending_positions(force=False) -> list[ShipHit]`, `set_position(id, position | None)`, `list_hits(since=None) -> list[ShipHitOut]`
- Produces: `ShipHitOut(ship_external_id, boat_slug, boat_number, name, date, tons, nationality, convoy, outcome, lat, lng, updated_at)`; `GET /api/uboats/ships?since=`

- [ ] **Step 1: Write the failing tests**

```python
async def test_upsert_refs_keeps_a_stored_position(tmp_path): ...
async def test_same_ship_hit_twice_is_stored_twice(tmp_path): ...
async def test_stopped_crawl_resumes_at_the_next_ship(tmp_path): ...
async def test_ship_without_a_position_is_not_retried_unless_forced(tmp_path): ...
async def test_failed_ship_is_retried_and_does_not_stop_the_crawl(tmp_path): ...
async def test_status_revision_moves_when_a_ship_is_stored(tmp_path): ...
async def test_ships_since_returns_only_changed_hits(tmp_path): ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/services/storage/test_ship_hit_repository.py tests/test_crawl_ships.py tests/http/api/test_ships.py -q`
Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement, mirroring `app/crawl.py`**

A network failure leaves `position_checked` false so that the ship is retried; only a page that loaded without a position sets it true. Hits become visible once stored, even before their position is known. Document the command and its runtime in the README.

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest -q`
Expected: all pass.

- [ ] **Step 5: Crawl the current 10 boats**

Run: `poetry run python -m app.crawl_ships`
Expected: progress per ship. Report the number of hits and how many have no position, and compare each boat's total with its `patrols.tonnage` sum, explaining any difference. Stored totals so far: U-101 121,976, U-607 44,138, U-4 6,223, U-355 5,082, U-3 2,348, U-143 1,409.

- [ ] **Step 6: Commit**

```bash
git add app tests README.md
git commit -m "Crawl ship hits and expose them through the API"
```

### Task 15: Ships on both maps

**Files:**
- Create: `frontend/js/ship-model.js`
- Modify: `frontend/js/api.js`, `frontend/js/map.js`, `frontend/js/status-map.js`, `frontend/js/sidebar.js`, `frontend/js/main.js`, `frontend/js/status.js`, `frontend/js/live.js`, `frontend/index.html`, `frontend/css/style.css`, `CONTEXT.md`
- Test: `frontend/tests/ship-model.test.js`, `frontend/tests/live.test.js`

**Interfaces:**
- Consumes: `GET /api/uboats/ships`, `startPolling`
- Produces: `fetchShips(since = null)`; `mergeShips(ships, changed)`; `shipsUpToDate(ships, date, followedSlug = null)`; `shipTotalsLine(ships) -> string`; `shipTooltip(ship) -> string`; `shipStyle(outcome) -> { color, fillColor, fillOpacity }`

- [ ] **Step 1: Write the failing tests**

```js
test("shipsUpToDate includes a ship on its own date, not the day before", ...);
test("shipsUpToDate limits to the followed boat", ...);
test("shipTotalsLine formats Dutch thousands and skips outcomes at zero", () => {
  assert.equal(shipTotalsLine(ships), "87 gezonken (412.000 ton) · 5 beschadigd (37.965 ton)");
});
test("shipTotalsLine counts a ship without a position", ...);
test("shipTooltip names ship, tonnage, outcome, boat and date", () => {
  assert.equal(shipTooltip(magog), "Magog — 2.053 ton — gezonken door U-99 op 1940-07-05");
});
test("shipStyle distinguishes sunk, damaged and captured", ...);
test("poll fetches changed ships when the revision changes", ...);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test tests/`
Expected: FAIL because `ship-model.js` does not exist.

- [ ] **Step 3: Implement**

Use a canvas renderer for the ship layer on both maps. Skip ships without coordinates when drawing, and list them as `positie onbekend` under a followed boat. Keep the ship layer below route lines on `/status`, so that the red route stays visible. Add **Scheepstreffer** to `CONTEXT.md`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test tests/`
Expected: all pass.

- [ ] **Step 5: Verify in a real browser**

Step through a date before and after a known hit and confirm the ship appears, the tooltip and totals are right, a followed boat shows only its own ships, and `/status` shows all of them, updating during `poetry run python -m app.crawl_ships --slugs u99 --force`.

- [ ] **Step 6: Commit and phase gate**

```bash
git add frontend CONTEXT.md
git commit -m "Show ship hits and tonnage on both maps"
```

Ask the user to check the ships. Merge to `master` only after their approval.

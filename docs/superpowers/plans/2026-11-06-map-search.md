# Zoeken op de kaart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one search field on the map of `/`, `/status` and `/heatmap`. It finds places (through Photon, cached by the backend), boats, ships and Veldslagen. Choosing a place while placing a Veldslag puts its square there.

**Architecture:**
- The backend serves `GET /api/places`. It forwards the query to Photon at most once per second and keeps every answer in `uboats.db`.
- The frontend has two parts. A pure `search-model.js` matches app data. A `map-search.js` Leaflet control owns the field, the list, the keyboard, the debounce and the temporary marker.
- Each page wires its own sources and its own `onPick`.

**Tech Stack:**
- FastAPI with wireup, and SQLAlchemy async on SQLite.
- `requests`, run inside `asyncio.to_thread`. `httpx` is not installed.
- Leaflet 1.x and vanilla ES modules.
- Tests use `node --test` and pytest.

**Spec:** `docs/superpowers/specs/2026-11-06-map-search-design.md`

## Global Constraints

- Branch `uboat-map-search`, based on `master` 3328d75. `uboat-articles` is paused. Its `selectBattle(title)` has the same name and meaning as the one built here.
- UI text is Dutch. Use these exact strings: `Boten`, `Schepen`, `Veldslagen`, `Plaatsen`, `Niets gevonden.`, `Plaatsen zoeken…`, `Plaatsen zoeken mislukt.`. The field placeholder is `Zoek plaats, boot, schip of veldslag (Ctrl+K)`. Domain words follow `CONTEXT.md`: Veldslag, Eigen positie, Gevolgde boot.
- Photon is reached at `https://photon.komoot.io/api/?q=<q>&limit=5&lang=en`.
  - Send the User-Agent from `build_user_agent(settings.CRAWLER_CONTACT)`.
  - Use a 20 s timeout.
  - Send at most 1 request per second, process-wide.
- Cache table `place_searches`, with columns `query` (PK, lowercased and trimmed), `results_json` and `fetched_at`. It has no expiry. Only successful answers are cached, and that includes `[]`.
- `GET /api/places?q=`:
  - It returns 422 for a blank or over-long `q` (over 200 characters after trimming), and 503 with a Dutch `detail` when Photon fails.
  - It is open to every client.
  - It returns at most 5 entries, each `{name, sub, lat, lng, bbox: [south, north, west, east] | null}`.
- Frontend timing:
  - The place fetch starts 400 ms after the last keystroke, and only when the trimmed text is at least 3 characters long.
  - Only the answer for the latest text is shown.
  - Each app group shows at most 5 results.
  - A place jump zooms to at most 10.
  - The temporary marker lives 30 s.
- Which sources each page searches: `/` searches boats, ships, Veldslagen and places. `/status` and `/heatmap` search Veldslagen and places.
- Tests: `poetry run pytest` and `cd frontend && node --test tests/` must both be green after every task.

## Review Focus

1. **Typing fast or deleting text:**
   - Expected: an answer for an older text must never overwrite the list for the current text.
   - Expected: emptying the field cancels the pending fetch.
   - Test: Task 2.
2. **Two browser tabs or quick queries that hit the backend at once:**
   - Expected: the 1 req/s limit holds across concurrent requests.
   - Expected: a cache hit does not wait for the limit.
   - Test: Task 1.
3. **Photon answers 200 but with features that lack a `name`, an `extent`, or have odd coordinates:**
   - Expected: those features are skipped or get `bbox: null`, never a 500.
   - Test: Task 1.
4. **`Ctrl+K` while focus is in another input**, such as the battle search field, or **`Esc` while a Veldslag is being placed:**
   - Expected: `Ctrl+K` still focuses the map search.
   - Expected: `Esc` in the map search field only closes the list and does not cancel the edit.
   - Test: Task 2 for the first, Task 4 for the second.
5. **A place chosen while placing a Veldslag, then `Annuleer`:**
   - Expected: the Veldslag keeps its old position (or none).
   - Expected: after `Bewaar`, the new position is stored.
   - Test: Task 3.

---

### Task 1: `GET /api/places` with throttled Photon and a cache

**Files:**
- Create: `app/services/places/__init__.py`, `app/services/places/photon.py`, `app/services/storage/place_search_repository.py`, `app/http/api/places/__init__.py`, `app/http/api/places/search.py`
- Modify: `app/services/storage/models.py` (adds `PlaceSearch`)
- Test: `tests/services/places/test_photon.py`, `tests/http/api/test_places.py`

**Interfaces:**
- Produces:
  - `parse_photon(payload: dict) -> list[dict]`, giving at most 5 `{name, sub, lat, lng, bbox}`.
  - `class PhotonClient` (`@injectable`), with `async search(query: str) -> list[dict]`. It raises `PhotonError` on a timeout, a status other than 200, or bad JSON. Its constructor takes `fetch=None`, `clock=time.monotonic` and `sleep=asyncio.sleep` as overridable parameters for tests. The default `fetch` does a `requests.get` with the User-Agent and a 20 s timeout, run in `asyncio.to_thread`.
  - `PlaceSearchRepository(session)`, with `async get(query) -> list | None` and `async put(query, results)`.
  - `RequestHandler.search_places(q: str) -> list[PlaceOut]`, served at route `/api/places`.
  - The API answers with the JSON shape given in Global Constraints.

- [ ] **Step 1: Write the failing tests**, following the handler-direct style of `tests/http/api/test_battle_positions.py` with a temp db:
  - `test_parse_maps_feature`:
    - Input: the real Narvik feature.
    - Expected: `name == "Narvik"`, `sub == "Nordland, Norge"`, `lat == 68.2898873` and `lng == 17.0865077`.
    - Expected: `bbox == [67.9693704, 68.6084547, 15.9014286, 18.1513549]`, from `extent [w, n, e, s]` → `[s, n, w, e]`.
  - `test_parse_skips_nameless_and_tolerates_missing_extent`:
    - Expected: a feature with no `name` is left out.
    - Expected: a feature with no `extent` gets `bbox is None`.
    - Expected: a feature whose `coordinates` are not 2 numbers is left out.
    - Expected: more than 5 features are cut to 5.
  - `test_client_spaces_requests_one_second`:
    - Setup: fake clock and sleep, two concurrent `search` calls through `asyncio.gather`.
    - Expected: the recorded sleep makes the second call start ≥ 1.0 s after the first.
  - `test_client_sends_user_agent`: the fake `fetch` receives headers whose `User-Agent` equals `build_user_agent(contact)`.
  - `test_cache_miss_then_hit`:
    - Expected: the first `search_places("  Narvik ")` calls the client once.
    - Expected: `search_places("narvik")` then does not call it again and returns the same list.
  - `test_empty_result_is_cached`: covered by the same check with `[]`.
  - `test_blank_and_long_query_422`: `"   "` and `"x" * 201` both raise `HTTPException(422)`.
  - `test_photon_failure_503_not_cached`:
    - Setup: the client raises `PhotonError`.
    - Expected: `HTTPException(503)` with a Dutch detail.
    - Expected: the next call reaches the client again.
- [ ] **Step 2: Run** `poetry run pytest tests/services/places tests/http/api/test_places.py -v`. Expected: FAIL (import errors).
- [ ] **Step 3: Implement.** Add `PlaceSearch` to `models.py` next to `BattlePosition`, with `fetched_at` as `UTCDateTime`. `init_models`' `create_all` creates the new table in the real `uboats.db`. Throttle with one `asyncio.Lock` held around "wait until `last + 1.0`, then fetch, then set `last`". The handler validates `q` first, then checks the cache, and only calls the client on a miss.
- [ ] **Step 4: Run** the same command. Expected: PASS. Then `poetry run pytest -q`, all green.
- [ ] **Step 5: Smoke test.**
  - Run `poetry run uvicorn app.main:app --port 8007`, then `curl -s 'localhost:8007/api/places?q=Narvik'`. Expected: 1 to 5 entries, the first named Narvik.
  - A second curl answers from the cache. Check this in the uvicorn log, or by timing it under 50 ms.
  - Stop the server afterwards.
- [ ] **Step 6: Commit:** `Look up places through Photon, cached and at most once a second`.

### Task 2: The search field and its list

**Files:**
- Create: `frontend/js/search-model.js`, `frontend/js/map-search.js`
- Modify: `frontend/js/api.js` (adds `fetchPlaces`), `frontend/css/style.css` (or the stylesheet where `.battle-search` lives)
- Test: `frontend/tests/search-model.test.js`, `frontend/tests/map-search.test.js` (use the fake-DOM approach of `frontend/tests/battle-dom.js`)

**Interfaces:**
- Consumes: Task 1's JSON.
- Produces:
  - `fetchPlaces(query, { signal }) -> Promise<Place[]>`, which throws on a status other than 200.
  - In `search-model.js`, each source function returns `[{ label, sub, item }]` with at most 5 entries. Matching is case-insensitive and finds substrings:
    - `matchBoats(boats, q)` matches `number` and `name`;
    - `matchShips(ships, q)` matches `name` and drops duplicate `ship_external_id`;
    - `matchBattles(battles, q)` matches `title` and `place`.
  - `createMapSearch({ map, sources, onPick, fetchPlaces, doc = document, win = window, delayMs = 400, markerMs = 30000 })` returns `{ showPlace(place), clear() }`.
    - `sources` is a list of `{ group, search(q) }`, in display order. Places always come last under `Plaatsen`.
    - `onPick({ group, item })` is called with `group` set to `"Boten"`, `"Schepen"`, `"Veldslagen"` or `"Plaatsen"`.
    - `showPlace` does `fitBounds` (with `maxZoom: 10`), or `setView(zoom 10)` when the place has no bbox. It then draws an `L.marker` with the name as a tooltip and removes it after `markerMs`, on the next `showPlace`, or on `clear()`.

- [ ] **Step 1: Write the failing tests:**
  - `search-model`:
    - each matcher finds case-insensitive substrings;
    - each matcher caps at 5;
    - `matchShips` drops duplicate ids;
    - an empty or blank query returns `[]`.
  - `map-search`, using `mock.timers` and a fake `fetchPlaces` that records its calls:
    - typing `"nar"` shows the app groups straight away. `fetchPlaces` is called exactly once, after 400 ms, with `"nar"`, and not for `"n"` or `"na"`.
    - typing `"nar"` and then `"narv"` within 400 ms gives one call, with `"narv"`.
    - an answer for `"nar"` that resolves after the one for `"narv"` is ignored (Review Focus 1).
    - clearing the field before 400 ms gives no call.
    - `ArrowDown`, `ArrowDown`, `Enter` calls `onPick` with the second row.
    - a rejected `fetchPlaces` shows `Plaatsen zoeken mislukt.` while the app groups stay.
    - no results anywhere shows `Niets gevonden.`
    - `Esc` closes the list and blurs the field.
    - `Ctrl+K` on `doc`, while focus is in another input, focuses the field and calls `preventDefault` (Review Focus 4).
    - `showPlace` adds a marker that is gone after 30 s.
- [ ] **Step 2: Run** `cd frontend && node --test tests/search-model.test.js tests/map-search.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - The control is an `L.control({ position: "topleft" })`. Call `L.DomEvent.disableClickPropagation` and `disableScrollPropagation` on it.
  - Rows are built with `textContent` only, never with `innerHTML`.
  - Each fetch carries an `AbortController`; the previous one is aborted when the text changes.
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Commit:** `Add a map search field for places and app data`.

### Task 3: Select a Veldslag by title and move the edit square

**Files:**
- Modify: `frontend/js/battles.js`, `frontend/js/battle-layer.js`
- Test: `frontend/tests/battles.test.js`, `frontend/tests/battle-layer.test.js`

**Interfaces:**
- Produces:
  - `initBattles(...)` now also returns `selectBattle(title) -> boolean`, `allBattles() -> Battle[]` and `moveEditTo(lat, lng) -> boolean`.
    - `selectBattle` behaves like a click on the row: it opens the split, marks the Veldslag in the list and on the map, reveals the row, and pans when the Veldslag has a position. It returns `false` for an unknown title, or when the battles have not loaded yet.
    - `allBattles` returns the battles after `applyPositions`, for `matchBattles`.
    - `moveEditTo` returns `false` when no edit is active.
  - `battle-layer` `startEdit(...)`'s handle gains `moveTo(lat, lng)`. It sets the marker and `position()`, using `wrapLng`, and pans the map to it.

- [ ] **Step 1: Write the failing tests:**
  - `selectBattle("Battle of Kursk")` after loading marks its row selected and returns `true`. `selectBattle("Nope")` returns `false`, and nothing changes.
  - During an edit, `moveEditTo(68.4, 17.4)` returns `true`, then `Bewaar` calls `savePosition` with `(title, 68.4, 17.4)`.
  - Without an edit, `moveEditTo` returns `false`.
  - During an edit, `moveEditTo` followed by `Annuleer` makes no save, and the Veldslag keeps its old `lat`/`lng` (Review Focus 5).
  - In `battle-layer`, `handle.moveTo(10, 200)` gives `position()` `{lat: 10, lng: -160}`.
- [ ] **Step 2: Run** `cd frontend && node --test tests/battles.test.js tests/battle-layer.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement.** Reuse the existing `onSelect` path of the pane for `selectBattle`, so a list click and a search choice run the same code.
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Commit:** `Select a battle by title and move the square being placed`.

### Task 4: Wire the search into the three pages

**Files:**
- Modify: `frontend/js/main.js`, `frontend/js/status.js`, `frontend/js/heatmap.js`, plus `CONTEXT.md` (term **Zoeken op de kaart**, one line)
- Test: by hand. The pages have no node tests for their wiring. Keep the wiring thin.

**Interfaces:**
- Consumes: Tasks 2 and 3, and on `/` also `followBoat(slug)`, `boatPanel.openShip(ship)`, `timeline.setDate`, the loaded `boatsBySlug` and the ships list.
- `onPick` per group:
  - `Boten`: call `followBoat(slug)`, then open the boat panel the way a boat click does.
  - `Schepen`: call `boatPanel.openShip(ship)` and `timeline.setDate(parseDate(ship.date))`, then `map.setView([lat, lng], max(zoom, 6))` when the ship has a position.
  - `Veldslagen`: call `battles.selectBattle(item.title)`.
  - `Plaatsen`: call `if (!battles.moveEditTo(item.lat, item.lng)) search.showPlace(item)`.
- In the edit bar's `Esc` handler (`battles.js` `onKey`), ignore events whose target is inside the map search control, so `Esc` in the field only closes the list (Review Focus 4). Add a test for this to `battles.test.js`.

- [ ] **Step 1: Write the failing test** for the `Esc` rule above. Run `cd frontend && node --test tests/battles.test.js`. Expected: FAIL.
- [ ] **Step 2: Implement** the `Esc` rule and the wiring on all three pages.
- [ ] **Step 3: Run** `cd frontend && node --test tests/` and `poetry run pytest -q`. Expected: PASS.
- [ ] **Step 4: Manual check** in a browser on `poetry run uvicorn app.main:app --port 8007`. Copy the full `frontend/battles/battles.json` from the main checkout in temporarily, then restore the committed one before committing.
  - On `/`:
    - `Ctrl+K`, then type `U-99`: the boat appears, and choosing it makes it the Gevolgde boot.
    - Type `Narvik`: places appear after the pause, and choosing one jumps there with a marker.
    - A Veldslag result selects it.
  - On `/status` and `/heatmap`: only Veldslagen and places appear.
  - Click `Positie aanpassen` on a Veldslag without a position, then search `Narvik` and choose the place: the square moves there. Then:
    - `Esc` in the field keeps the edit;
    - `Bewaar` stores it;
    - after a reload, the list shows `eigen positie`.
  - The field fits beside the zoom buttons at 1920 px and does not break the layout at 390 px.
- [ ] **Step 5: Commit:** `Search the map on the map, boat and heatmap pages`.

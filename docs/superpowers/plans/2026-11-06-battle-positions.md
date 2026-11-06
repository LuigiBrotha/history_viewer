# Eigen positie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** From the laptop, the user can place or move any Veldslag on the map by dragging, or clear that again. The Eigen positie is stored in `uboats.db` and wins over the Wikipedia position on all three map pages.

**Architecture:** A `battle_positions` table with a small loopback-guarded REST API (GET for everyone; PUT and DELETE only from this machine). The frontend merges the positions into the battles after loading `battles.json`. The battle layer gets a dashed style and a single-square edit mode (Leaflet marker dragging plus a small Bewaar/Annuleer bar). The battle pane gets the buttons.

**Tech Stack:** FastAPI with wireup class-based handlers, SQLAlchemy async, SQLite; plain ES modules with `node --test`; Leaflet 1.9.4.

**Spec:** `docs/superpowers/specs/2026-11-06-battle-positions-design.md`

## Global Constraints

- UI text is Dutch, exactly: `Positie aanpassen`, `Eigen positie wissen`, `Bewaar`, `Annuleer`, `eigen positie`, `geen positie`, `Bewaren mislukt.`
- Edits are only allowed from this machine: use `require_loopback` from `app/http/loopback.py`, as `app/http/api/uboats/excluded_points.py` does. The frontend shows the buttons only when `/api/uboats/status` says `can_edit`.
- Titles are source data: they only reach the page as text content, never as HTML.
- The table is keyed by the Veldslag's title as in `battles.json`, so it survives a new extraction.
- Tests: `poetry run pytest` and `cd frontend && node --test tests/` are green after every task.

## Review Focus

1. **A title with `/`, `&`, quotes or non-ASCII characters** (`Battle of the Bulge (1944–45)`, `Operation "Weserübung"`): the PUT and DELETE paths must keep it intact → tests in Task 1 and Task 2.
2. **A drag past the date line** gives a longitude outside [-180, 180]: the frontend wraps it before sending → test in Task 3.
3. **The positions request fails or is slow**: the battles still show with their Wikipedia positions, and editing is simply not offered until the positions have loaded → test in Task 2.
4. **The user changes the date or period while editing**: the dragged square must not vanish or reset → test in Task 3.
5. **Save fails** (network error, 403 from another machine): the bar says `Bewaren mislukt.`, stays in edit mode, and the square keeps its dragged place → test in Task 4.

---

### Task 1: Store and serve Eigen posities

**Files:**
- Modify: `app/services/storage/models.py`
- Create: `app/services/storage/battle_position_repository.py`, `app/services/battles/__init__.py`, `app/services/battles/known_battles.py`, `app/http/api/battles/__init__.py`, `app/http/api/battles/positions.py`
- Test: `tests/services/storage/test_battle_position_repository.py`, `tests/http/api/test_battle_positions.py`

**Interfaces:**
- Produces:
  - `class BattlePosition(Base)`, `__tablename__ = "battle_positions"`: `title: str` PK, `lat: float`, `lng: float`, `updated_at` (`UTCDateTime`, as the other models use).
  - `BattlePositionRepository(session)`:
    - `async all() -> list[tuple[str, float, float]]`
    - `async put(title, lat, lng) -> None` (upsert)
    - `async delete(title) -> None` (no error if absent)
  - `known_battle_titles() -> frozenset[str]`: the titles in `FRONTEND_DIR / "battles" / "battles.json"`, cached and re-read when the file's mtime changes. The path is a parameter with that default, so tests pass their own file.
  - Routes (class `RequestHandler`, the same pattern as `excluded_points.py`):
    - `GET /api/battles/positions` → `[{"title", "lat", "lng"}]`
    - `PUT /api/battles/positions/{title:path}`, body `{"lat": float, "lng": float}` → the stored `{"title", "lat", "lng"}`
    - `DELETE /api/battles/positions/{title:path}` → 204
    - PUT and DELETE use `dependencies=[Depends(require_loopback)]`. PUT answers 422 when lat is outside [-90, 90] or lng outside [-180, 180] (pydantic `Field(ge=…, le=…)`), and 404 `{"detail": "Onbekende veldslag."}` when the title is not in `known_battle_titles()`.

- [ ] **Step 1: Write the failing tests.**
  - Repository: put → all; put the same title again → replaced; delete → gone; delete of an absent title does not raise.
  - `known_battle_titles` re-reads after the file changes. Use `os.utime` to bump the mtime.
  - Handlers, called directly as in `tests/http/api/test_excluded_points.py` (read it for how loopback and non-loopback requests are faked):
    - GET returns the stored rows.
    - PUT stores and returns the row; PUT with lat 91 → 422; PUT for an unknown title → 404.
    - PUT and DELETE from a non-loopback request → 403.
    - DELETE → 204, and a later GET no longer lists it.
    - Review Focus 1: `Battle of the Bulge (1944–45)` and `Operation "Weserübung"` round-trip through PUT/GET/DELETE.
- [ ] **Step 2: Run** `poetry run pytest tests/services/storage/test_battle_position_repository.py tests/http/api/test_battle_positions.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** `init_models` creates the new table through `create_all`. Check that `poetry run python -c "import app.main"` still works.
- [ ] **Step 4: Run** `poetry run pytest`. Expected: PASS.
- [ ] **Step 5: Commit:** `Store and serve hand-placed battle positions`.

### Task 2: Merge Eigen posities into the battles

**Files:**
- Modify: `frontend/js/api.js`, `frontend/js/battle-model.js`, `frontend/js/battles.js`
- Test: `frontend/tests/api.test.js`, `frontend/tests/battle-model.test.js`, `frontend/tests/battles.test.js`

**Interfaces:**
- Produces:
  - `api.js`:
    - `fetchBattlePositions(): Promise<{title, lat, lng}[]>`
    - `saveBattlePosition(title, lat, lng): Promise<{title, lat, lng}>`
    - `clearBattlePosition(title): Promise<void>`
    - Titles are always passed through `encodeURIComponent`. A non-ok response throws an `Error`. Use a 30 s timeout, like the other helpers.
  - `battle-model.js`:
    - `applyPositions(battles, positions): battle[]` returns new objects. A battle with an Eigen positie gets `lat`/`lng` from it plus `own: true`. Every battle keeps `wikiLat`/`wikiLng`, the values from the file. Other battles are returned unchanged apart from `wikiLat`/`wikiLng`.
    - `wrapLng(lng): number` returns the equivalent longitude in [-180, 180].
  - `battles.js`: `initBattles({ ..., loadPositions = fetchBattlePositions })` loads both. When `loadPositions` rejects, the battles still render from the file only, with `console.error`. It keeps the merged list as its `battles`.

- [ ] **Step 1: Write the failing tests.**
  - `applyPositions`:
    - a battle without a file position gets one;
    - a battle with a file position is overridden and keeps `wikiLat`;
    - a position for an unknown title is ignored;
    - the input objects are not mutated.
  - `wrapLng`: `190 → -170`, `-190 → 170`, `540 → 180` or `-180` (either is accepted), `45 → 45`.
  - `api.js`: the URL encodes `Operation "Weserübung"`.
  - `battles.js` (Review Focus 3): with `loadPositions` rejecting, the squares from the file are still drawn. With it resolving, the square sits at the Eigen positie.
- [ ] **Step 2: Run** `cd frontend && node --test tests/`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Commit:** `Place battles at their hand-set position when there is one`.

### Task 3: Dashed squares and dragging in the battle layer

**Files:**
- Modify: `frontend/js/battle-layer.js`, `frontend/css/style.css`
- Test: `frontend/tests/battle-layer.test.js`

**Interfaces:**
- Consumes: `wrapLng` (Task 2).
- Produces:
  - Squares of battles with `own: true` get the class `battle-square own`. The CSS gives `.battle-square.own span` a dashed border. The selected styling still applies on top.
  - `layer.startEdit(battle, { onMove })`:
    - Makes that battle's square draggable (`marker.dragging.enable()`). A battle without `lat`/`lng` first gets a square at `map.getCenter()`.
    - Returns `{ position(): {lat, lng}, stop(): void }`. The position is wrapped with `wrapLng`.
    - `onMove(position)` is called on `dragend`.
    - The square being edited is always drawn, even when it is outside the battles last given to `setBattles` (Review Focus 4) or out of view.
    - `stop()` disables dragging and redraws from the current battles.
    - Starting a new edit stops the previous one.
- [ ] **Step 1: Write the failing tests.** Extend the fake `L.marker` in `battle-layer.test.js` with `dragging: { enable, disable, enabled }`, `getLatLng` and a `dragend` event, and give the fake map `getCenter`. Tests:
  - an `own` battle's icon class contains `own`;
  - `startEdit` on a battle with a position enables dragging on its marker only;
  - `startEdit` on a battle without a position adds a square at the centre;
  - after a fake drag to `lng 190`, `position()` returns `lng -170` and `onMove` received it;
  - `setBattles([])` during the edit keeps the edited square (Review Focus 4);
  - `stop()` disables dragging, and a battle without a position loses its temporary square.
- [ ] **Step 2: Run** `cd frontend && node --test tests/battle-layer.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Commit:** `Draw hand-placed battles dashed and let one square be dragged`.

### Task 4: Buttons, edit bar and page wiring

**Files:**
- Modify: `frontend/js/battle-pane.js`, `frontend/js/battles.js`, `frontend/js/main.js`, `frontend/js/status.js`, `frontend/js/heatmap.js`, `frontend/css/style.css`, `README.md`, `CONTEXT.md`
- Test: `frontend/tests/battle-pane.test.js`, `frontend/tests/battles.test.js`

**Interfaces:**
- Consumes: Tasks 2 and 3.
- Produces:
  - `battle-pane.js`:
    - Each row's meta shows `eigen positie` (class `battle-ownpos`) for `own` battles, and `geen positie` as now for battles without any position.
    - `pane.setEditable(bool)`.
    - When editable, the **selected** row (the one `reveal` marked) shows a button `Positie aanpassen`. For an `own` battle it also shows `Eigen positie wissen`. The buttons call `onEdit(battle)` and `onClear(battle)`, new options of `createBattlePane`.
  - `battles.js` returns `setEditable(bool)` besides `setDate`/`setPeriod`. Edit flow:
    - `onEdit` selects and reveals the battle, then calls `layer.startEdit`.
    - It adds a Leaflet control at `topleft` with class `battle-edit-bar`, holding the title as text and the buttons `Bewaar` and `Annuleer`.
    - Esc on the document equals Annuleer.
    - Bewaar disables both buttons and awaits `saveBattlePosition(title, lat, lng)`, injectable as `savePosition`. On success it updates the battle with `own: true`, removes the bar, stops the edit, and re-applies the list and layer. On failure the bar shows `Bewaren mislukt.`, the buttons are enabled again, and edit mode stays (Review Focus 5).
    - `onClear` awaits `clearBattlePosition` (injectable as `clearPosition`) and restores `wikiLat`/`wikiLng`; `own: false`.
    - Selecting another battle or `setEditable(false)` cancels an edit.
  - Pages:
    - `main.js` calls `battles.setEditable(canEdit(status))` in its existing `onStatus`.
    - `status.js` and `heatmap.js` do the same in their `onStatus`. They import `canEdit` from `api.js`.
  - `CONTEXT.md` gets the term **Eigen positie**:
    - "Een positie die de gebruiker zelf aan een Veldslag heeft gegeven. Gaat voor op de positie uit Wikipedia en kan weer worden gewist."
    - _Avoid_: handmatige locatie, override.
- [ ] **Step 1: Write the failing tests.**
  - Pane: the buttons appear only when editable and only on the selected row. `Eigen positie wissen` appears only for `own`. The label `eigen positie` is shown for `own`.
  - `battles.js` with fake `savePosition`/`clearPosition` and the fake layer:
    - Bewaar sends the dragged position and turns the square dashed.
    - A rejected save shows `Bewaren mislukt.` and keeps edit mode.
    - Annuleer and Esc restore the old place.
    - Clearing restores the Wikipedia position.
    - `setEditable(false)` cancels the edit and hides the buttons.
- [ ] **Step 2: Run** `cd frontend && node --test tests/`. Expected: FAIL.
- [ ] **Step 3: Implement.** Add CSS for `.battle-edit-bar` (a small white box like the other map controls) and for the row buttons.
- [ ] **Step 4: Run** `cd frontend && node --test tests/` and `poetry run pytest`. Expected: PASS.
- [ ] **Step 5:** Add one paragraph to `README.md` on Eigen positie. **Commit:** `Let the user place and move battles on the map`.
- [ ] **Step 6 (controller): browser check** on `/`, `/status` and `/heatmap`:
  - place a battle that has no position;
  - move one that has a position;
  - reload, and both stay;
  - clear one;
  - check that Esc cancels.

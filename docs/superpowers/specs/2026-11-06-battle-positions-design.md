# Eigen positie for Veldslagen — Design

Of the 1728 Veldslagen, 895 have no position; of the rest, some positions from Wikipedia are
wrong. The user places or moves a Veldslag on the map by hand. Domain terms are in `CONTEXT.md`.

Decided with the user (2026-11-06):

| Topic | Decision |
|---|---|
| Method | By hand only; no automatic geocoding. |
| Which | Every Veldslag, also one with a position from Wikipedia. An Eigen positie wins; clearing it brings the Wikipedia position (or none) back. |
| How | The selected Veldslag's row in the list gets **Positie aanpassen**. That makes only its square draggable. A Veldslag without a position first appears in the middle of the map. A small bar on the map offers **Bewaar** and **Annuleer**; Esc also cancels. A row with an Eigen positie also gets **Eigen positie wissen**. |
| Seen as | On the map a square with an Eigen positie has a dashed border. In the list its row says `eigen positie` where it now says `geen positie` (or nothing). |
| Who | Only from the laptop itself (loopback), exactly like excluded route points; elsewhere the buttons are not shown and the API answers 403. |
| Survives | A new extraction of `battles.json`: the positions live in `uboats.db`, keyed by the Veldslag's title. |
| Pages | All three map pages (`/`, `/status`, `/heatmap`). |

## Backend

| Topic | Decision |
|---|---|
| Table | `battle_positions(title PK, lat REAL, lng REAL, updated_at)`. |
| Read | `GET /api/battles/positions` → `[{title, lat, lng}]`, everyone. |
| Write | `PUT /api/battles/positions/{title:path}` with `{lat, lng}` → `{title, lat, lng}`; `DELETE /api/battles/positions/{title:path}` → 204. Both `require_loopback`. |
| Validation | lat in [-90, 90], lng in [-180, 180] (a dragged square may report a wrapped longitude: the frontend wraps it into range first); 422 otherwise. The title must be a Veldslag in `frontend/battles/battles.json` (read once, re-read when its mtime changes); 404 otherwise. DELETE of a title without an Eigen positie is 204 as well. |

## Frontend

| Topic | Decision |
|---|---|
| Loading | `battles.js` fetches `battles.json` and the positions together. A pure `applyPositions(battles, positions)` returns new records: those with an Eigen positie get its `lat`/`lng` and `own: true`; the Wikipedia values are kept as `wikiLat`/`wikiLng`. If the positions cannot be loaded, the battles still show (Wikipedia positions only). |
| Editable | The pages already read `can_edit` from `/api/uboats/status`; they pass it to `initBattles` (`setEditable(bool)`). |
| Edit mode | One Veldslag at a time. Starting it selects the Veldslag, pans to it, and makes its square draggable (for one without a position: placed at the map's centre). Bewaar sends PUT, then the square stays where it is, now dashed; Annuleer/Esc puts it back. While saving, the buttons are disabled; on an error the bar shows `Bewaren mislukt.` and stays in edit mode. Selecting another Veldslag or starting a new edit cancels the current one. |
| Clearing | Eigen positie wissen sends DELETE and restores the Wikipedia position (or removes the square). |
| The period filter | A square being edited stays visible even if the date or period changes. |

## Testing

- Backend: repository and endpoints (read, put, replace, delete, 403 from non-loopback, 422 out of range, 404 unknown title).
- Frontend (node): `applyPositions`; the layer's dashed class and edit mode (draggable, centre placement, save/cancel, Esc); the pane's buttons and labels only when editable; the wiring in `battles.js` with a fake API.
- Manual: in a browser, place a Veldslag without position, move one with a position, clear it again, reload.

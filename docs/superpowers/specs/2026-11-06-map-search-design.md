# Zoeken op de kaart

Date: 2026-11-06. Agreed with the user on 2026-11-06, one question at a time. Built on branch `uboat-map-search`, off `master` (3328d75). `uboat-articles` is paused.

## Goal

The user wants a single search field for finding places, boats, ships and Veldslagen on the map. The main use is placing Veldslagen without a position: the user looks up the place named in the article and puts the Veldslag there.

## Where

- There is one search field at the top left of the map, next to the zoom buttons, as a Leaflet control at `topleft`. It is on `/`, `/status` and `/heatmap`.
- `Ctrl+K` (and `Cmd+K`) puts the focus in the field, even while focus is elsewhere on the page. `Esc` closes the result list and leaves the field.

## Results

The field searches two sources:

- **App data**, searched as the user types in the browser, with no network traffic.
  - Boats: number and name, `/` only.
  - Ships: name, `/` only.
  - Veldslagen: title and place, all three pages.
  - Matching is case-insensitive and finds substrings. Each group shows at most 5 results.
- **Places**, from Photon (`photon.komoot.io`, OpenStreetMap data). The user chose Photon over Nominatim on 2026-11-06 because Photon allows search-as-you-type.
  - Places are fetched while the user types, 400 ms after the last keystroke and from 3 characters on.
  - The list only ever shows the answer to the latest text: an older answer that arrives later is dropped.
  - `Enter` while the field still has no answer fetches places straight away.
  - The list shows at most 5 places. A place's label is its `name`; the line below it is `city`, `county`, `state` and `country`, whichever Photon gives (checked against a real answer for Narvik on 2026-11-06), joined with `, `.

The list groups results under the headings `Boten`, `Schepen`, `Veldslagen` and `Plaatsen`. Arrow keys move through the list and `Enter` chooses. If no group has a result, the list says `Niets gevonden.` While places load, the `Plaatsen` group says `Plaatsen zoeken…`, and the app groups already show. If loading fails, it says `Plaatsen zoeken mislukt.`

## Choosing a result

Choosing a result does the same as clicking that thing on the map:

- **Boat:** it becomes the Gevolgde boot and the boat panel opens.
- **Ship:** the ship panel opens, the map moves to the ship's position and the timeline moves to its date.
- **Veldslag:** the Veldslag is selected, as if the user had clicked it in the list. Its row is revealed and the map pans to it when it has a position.
- **Place:** the map jumps there. It zooms to the place's bounding box, at most zoom 10. A temporary marker shows the place with its name as a tooltip. The marker goes away on the next choice, on `Esc` in the field, or after 30 seconds.
- **Place while placing a Veldslag** (`Positie aanpassen` is active): the draggable square moves to the place and the map follows. The user can still drag the square, then press `Bewaar`, or `Annuleer`. No temporary marker is shown.

## Backend: `GET /api/places?q=…`

- Read-only and open to every client. Editing positions stays loopback-only.
- Without `q`, or with a blank `q` after trimming, the endpoint returns 422. A `q` longer than 200 characters also returns 422.
- The answer is `[{ "name": str, "sub": str, "lat": float, "lng": float, "bbox": [south, north, west, east] | null }]`, at most 5 entries.
- The request it sends is `https://photon.komoot.io/api/?q=<q>&limit=5&lang=en`. Photon has no Dutch; English matches the Wikipedia names of the Veldslagen.
  - The answer is GeoJSON. Each feature becomes `{name, lat, lng, bbox, sub}`:
    - `lat` and `lng` come from `geometry.coordinates`, given as `[lng, lat]`;
    - `bbox` comes from `properties.extent`, given as `[west, north, east, south]`, or is `null`;
    - `sub` is the line described above;
    - a feature with no `name` is skipped.
  - User-Agent comes from `build_user_agent(CRAWLER_CONTACT)` in `app/services/scraping/uboat_net/http_client.py`, with timeout 20 s.
  - At most 1 request per second goes out, process-wide. An async lock plus the time of the last request enforce this, and a waiting request queues behind the lock.
- **Cache:** the table `place_searches` in `uboats.db` stores `query` (lowercased and trimmed, primary key), `results_json` and `fetched_at`. A hit answers without contacting Photon. Places do not move, so there is no expiry. Only successful answers are cached, and that includes an empty list.
- If Photon fails (timeout, a status other than 200, or bad JSON), the endpoint returns 503 with a Dutch `detail` and caches nothing.

## Frontend modules

- `frontend/js/map-search.js` holds `createMapSearch({ map, sources, onPick, fetchPlaces })`. It owns the control, the list, the keyboard handling and the temporary marker.
  - `sources` is a list of `{ group, search(query) → [{ label, sub?, item }] }`.
  - `onPick({ group, item })` is called on every choice, places included. For a place, the page decides whether to move an edit square or to show the marker; for the marker it calls `search.showPlace(place)`.
- `frontend/js/search-model.js` holds the pure matching functions for each source, tested in node.
- `battles.js` gains two functions:
  - `selectBattle(title)`, which uses the same name and meaning as on branch `uboat-articles` to keep the later rebase small;
  - `moveEditTo(lat, lng)`, which returns `false` when no edit is active.
- `battle-layer.js` gives the handle from `startEdit` a `moveTo(lat, lng)`.

## Out of scope

- Historical place names: Photon knows today's names.
- Remembering recent searches, and search text in the URL.
- Searching patrols or dates.

## Tests

- pytest:
  - a cache miss goes out once and the second call answers from the cache;
  - an empty `q` returns 422 and an over-long `q` also returns 422;
  - a Photon failure returns 503 and is not cached;
  - two requests are at least 1 s apart, tested with an injected clock and sleep;
  - the User-Agent header is the one described above;
  - a Photon GeoJSON answer is mapped to the response fields, with `extent` reordered and features without a name skipped.
- node:
  - the matching functions in `search-model.js`;
  - in `map-search`:
    - typing shows the app groups at once;
    - typing calls `fetchPlaces` once, after the pause, for the last text and not for shorter texts;
    - an answer that arrives late for an older text is dropped;
    - the arrow keys and `Enter` call `onPick`;
    - `Esc` closes the list;
    - `Ctrl+K` focuses the field;
  - `moveEditTo` moves the edit square, and `Bewaar` saves that position.

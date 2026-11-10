# uboats

Scraper, API and Leaflet map for U-boat data and patrol routes from [uboat.net](https://uboat.net).

See `docs/superpowers/specs/` and `docs/superpowers/plans/` for the design and implementation plan.

## Setup

```
poetry install
cp .env.example .env
poetry run uvicorn app.main:app --reload
```

The app reads its configuration from `.env` (see `.env.example` for the full
list of settings and what each one does). None of the defaults need changing
for local development.

The map is at <http://localhost:8000> and needs an internet connection for
Leaflet and the map tiles. It stays empty until you have crawled some data (see
below).

### Viewing from another device

To open the map on a phone or another computer on your network, start the server on all interfaces:

```
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001 --no-proxy-headers
```

There is no login. Other devices are read-only: excluding or restoring a route
point is only accepted from the computer the server runs on (`127.0.0.1` or
`::1`, addressed as `localhost`, `127.0.0.1` or `[::1]`) and answers 403 to anyone else.
Keep `--no-proxy-headers`; requests carrying `X-Forwarded-For`, `Forwarded` or `X-Real-IP` are never editable anyway. `python -m app.main` binds to
`127.0.0.1` only.

## Pages and live updates

- `/dag-tot-dag` is the timeline map: a date slider shows which boats were on patrol and
  lets you follow one boat. It is designed mobile first; `‹` and `›` step one day.
- `/` shows every crawled patrol route at once as very thin dashed water
  routes, coloured by departure date on Google's Turbo ramp from the oldest to
  the newest patrol of the selected period. The patrol that was crawled last is black and on top. Drag
  the slider's handles, or the selection between them, to see only patrols
  overlapping that period; arrow keys work too. Hover or tap a
  route for its boat, patrol id and dates. The link `Tijdlijn` goes back to the
  timeline. The page is designed mobile first.

uboat.net often lists more positions for a patrol than dates, without saying
which belongs to which. Such positions are stored without a date. When read, they
are spread evenly between departure and arrival and shown as approximate: hollow
markers and `(datum benaderd)` in the tooltip. Speed checks never use these dates.

- `/heatmap` shows where U-boats were most active: the number of patrols passing
  through each half-degree cell, on the same draggable period slider. A patrol counts
  once per cell, and fully if it overlaps the period at all.

Click a boat on the timeline or a route on `/` for a panel with the boat's
details, its patrols and the ships it hit; click a patrol to show its route: a bottom sheet on a phone, a side panel on
larger screens. Click a ship on either map, or in a boat's list of ships hit, for a panel
with that ship: tonnage, outcome, position, and what its page on uboat.net says (owner,
cargo, fate, what happened), plus any other time it was hit.

All three pages also show World War II battles, taken from the English Wikipedia
(CC BY-SA 4.0): small amber squares with the battle's name on the map, and a pane with
all of them in a list, oldest first, each with its dates, duration and a bar on one
1939-1945 axis. The pane sits to the right of the map (drag the divider to resize it,
or use the arrow keys on it) and under the map on a phone; the `Veldslagen` button shows
or hides it. On `/dag-tot-dag` the squares are the battles active on the selected date, on `/`
and `/heatmap` those overlapping the selected period; the list always holds all of them,
the ones outside the selection dimmed. Clicking a row pans the map to its square, and
on `/dag-tot-dag` also sets the date to its start. The data is in `frontend/battles/battles.json`,
built by `tools/extract_battles.py` from the Wikipedia dump (see
`frontend/battles/README.md`); dates and coordinates are parsed automatically.

On this machine a battle's position can be corrected: select its row (or square), press
`Positie aanpassen`, drag the square and press `Bewaar` (`Annuleer` or Esc cancels). Such an
*Eigen positie* is stored by the battle's title, so it survives a new extraction, goes before
the Wikipedia position, is drawn dashed, and can be removed again with `Eigen positie wissen`.
A battle without a position can be given one this way too.

A square has the colour of the Kamp that won the battle (`winner` in `battles.json`), in the
colours of the atlas legend plus green for the rest (China, partisans, resistance); an undecided
battle is split diagonally between its two Kampen, and an unknown outcome stays amber. The
legend under the atlas legend explains them, and the Artikel starts with a `Winnaar:` line.

`Alleen zonder positie (N)` in the pane lists only the battles without any position under the
selected date or period. While it is ticked, the selected battle stays in the list even after
it gets a position, until another one is chosen.

Selecting a battle opens its *Artikel*: the Wikipedia article, rendered by the app itself from
the stored wikitext, in a resizable column beside the list. The articles are filled by the
extraction (`tools/extract_battles.py`, or `tools/fill_battle_articles.py` for the battles
already known; see `frontend/battles/README.md`). Images in an article are fetched once
by the server and kept in the image cache folder (`WIKI_IMAGE_DIR`).

Keyboard shortcuts on the map pages (press `?` for the overview): `↑`/`↓` previous or next
battle in the list, `P` Positie aanpassen, `Enter` Bewaar, `Shift+Enter` Bewaar en volgende
(on to the next battle without a position), `Esc` cancel, `W` wipe the Eigen positie (after confirming), `A`
article open or closed, `V` battle list open or closed, `/` or `Ctrl+K` search. Coordinates
typed into the search field (`52.37, 4.89`, `51°59′N 5°55′E`) can be chosen like a place.

The search field also offers *Labels* under "Filters": a Land (`Polen`), a Winnaar (`As`,
`onbeslist`, `onbekend`), a language (`Duits`) or a kind of position (`eigen positie`,
`Wikipedia-positie`), an Eenheid (`7th Panzer Division`) or a Bevelhebber (`Erwin Rommel`). An Eenheid or
Bevelhebber also draws its *Spoor*: its battles in date order, numbered and joined by a line with arrows,
whatever the date or period; a battle that holds a shorter one of the same Spoor (a campaign around its
battles) is left out. Chosen labels appear above the battle list with a ✕ and narrow the list and
the squares on the map; a battle must match all of them. The list can be sorted by date, name,
duration, Nog te verfijnen, or Afwijking (largest or smallest first: the km from where a battle
stands to the middle of its Plaatshints). The Landen, Bevelhebbers and Eenheden come from `poetry run python -m tools.enrich_battles`,
which reads the stored articles and, when present, the result of
`poetry run python -m tools.extract_unit_battles` (the battles listed in the articles of units and people).

Under the battle list, *Exporteren en back-up* downloads the listed battles (with their labels and search
applied) as CSV or GeoJSON, and all Eigen posities as a JSON back-up. On this machine a back-up can be
restored: where it differs from the stored positions it wins, positions it lacks stay, and the page asks
first, saying how many will change.

Every map page keeps its view in its URL, so a bookmark or copied link (a *Pin*) opens the
same view again: `datum` on `/dag-tot-dag`, `van` and `tot` on `/` and `/heatmap`, and on all three
`veldslag`, `kaart` (lat,lng,zoom), `boot` (on `/dag-tot-dag`), `zonderpositie=1`, `filter` and `sorteer`. The links between
the map pages carry the Veldslag, the Kaartuitsnede, the boat and `zonderpositie` along, not
the date or period.

Maps open on a background of ocean depth (Esri Ocean). A layer button switches to the
street map; the choice is remembered in the browser.

- `/grafiek` shows stacked bars of the cumulative sunk tonnage per day, week or month, with a block per boat. The eight biggest boats have a colour, the others are grey until you hover over them, search for them or pick them in the table. `poetry run python -m app.crawl_ships --lists-only` reads only each boat's list of ships, one request per boat.

All maps show a soft historical layer of who controlled what, from world maps on
Wikimedia Commons (CC BY-SA 3.0, see `frontend/atlas/README.md`). The timeline uses the
last map on or before the selected date, `/` the last map on or before the end of
the selection. The maps are coarse, about 25 km per pixel: they show the broad
situation per month, not exact borders.

On the first load a large indicator in the middle of the page shows the percentage of
patrols received, reading them page by page.
The server keeps all routes as ready JSON and only rebuilds patrols that changed; it
fills this in the background when it starts.

All pages poll the API every 5 seconds (paused while the tab is hidden), so
routes from a running crawl appear without reloading. Only changed patrols are
fetched. A status line shows when the last patrol was crawled; if the server
cannot be reached it shows `Geen verbinding, opnieuw proberen…` and keeps the
data already on screen. On `/dag-tot-dag` the selected date, zoom and followed boat are
kept across updates.

## Searching the texts

The search field above the column Onderwerpen looks in the names and in the full text of every
battle (all languages and the Dutch versions), boat and ship. It accepts typing errors and puts
the best results on top. It reads `search_index.db`, next to the database, which is built with:

    poetry run python -m tools.build_search_index

Run it again after new articles or translations came in. Without it, the field filters on names.

## Excluding route points

On `/dag-tot-dag`, follow a boat and click a route point: `Punt uitsluiten` leaves it out of
the patrol and the water routes are recomputed (the first time this can take a few
seconds). Excluded points are listed under the boat's status as `Uitgesloten punten`,
each with `Herstellen`. The exclusion is kept across recrawls. This works only in a
browser on the laptop itself; other devices see the list but no buttons.

## Tests

```
poetry run pytest
cd frontend && node --test tests/
```

## Crawling

Fetching boat and patrol data from uboat.net is a separate, standalone step --
it does not run inside the API process. It's resumable: a re-run skips boats
already recorded as successfully crawled unless `--force` is passed.

```
poetry run python -m app.crawl [--limit N] [--slugs u99,u100] [--force] [--delay N]
```

- `--limit N` — crawl at most N boats that still need it (already-successful
  boats are skipped before the limit is applied, so `--limit 50` run
  repeatedly chunks through the full listing rather than re-selecting the
  same boats).
- `--slugs u99,u100` — crawl only the given comma-separated boat slugs.
- `--force` — re-crawl boats even if already marked successful.
- `--delay N` — override `CRAWL_DELAY_SECONDS` (minimum seconds between
  requests to uboat.net; defaults to 10, matching the site's `robots.txt`
  crawl-delay).

With no flags, it crawls the full listing (~1153 boats), which at the
10-second-minimum crawl delay takes on the order of hours. Progress and any
per-boat failures are printed to stdout as the crawl runs.

The crawl also computes the shortest water route between consecutive route
points of each patrol (stored before the patrol appears). A routing failure is
printed and never fails the crawl. To fill in routes for patrols that are
already crawled:

```bash
poetry run python -m app.compute_water_routes [--force]
```

It skips legs that are already stored (`--force` recomputes them), bumps
`updated_at` of each patrol that got new legs so the status page picks them
up, and prints progress plus a summary per status. Loading the land data takes
about 5 seconds. `crawl --force` re-crawls boats but does not recompute stored
water routes; use the backfill with `--force` for that.

After upgrading to a version with water routes, run the backfill once: until then
both maps show no route lines and the status line says how many legs are not
computed yet. Rerun it after any crawl that was started by an older version, since
that crawl stores patrols without routes.

## Crawling ships hit

The ships each boat sank, damaged or captured are fetched by a second standalone
command, because their positions and details are only on the page of each ship:

```
poetry run python -m app.crawl_ships [--limit N] [--slugs u99,u100] [--force] [--delay N]
```

- Without `--slugs` it uses the boats in the database that sailed at least one patrol.
- A boat's list is read once: a later run skips the boats already listed and goes on
  with the ship pages.
- It reads each boat's list of successes (one request per boat) and stores the
  hits at once, so they show on the maps before their positions are known. Then it
  fetches the page of every hit whose position is unchecked or whose ship has no
  details yet (one request per ship, however often it was hit). One page gives the
  position and the details, so a database from an earlier version gets its details
  on the next run.
- `--limit N` — fetch the page of at most N ships in this run, for a small sample.
- `--force` — read every list again and fetch every page again, also for ships that already have one
  (a page without a position is otherwise not retried; ships that failed on the network always are).
- Requests are made one at a time with the same delay as the main crawl (10 s by
  default), so a boat with 40 ships takes about 7 minutes. Stopping loses at most
  the ship in flight; run it again to continue.

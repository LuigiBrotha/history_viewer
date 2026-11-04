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

## Pages and live updates

- `/` is the timeline map: a date slider shows which boats were on patrol and
  lets you follow one boat.
- `/status` shows every crawled patrol route at once, in blue. The patrol that
  was crawled last is drawn in red on top; hover a route for its boat and
  patrol id. The link `Tijdlijn` goes back to the timeline.

Both pages poll the API every 5 seconds (paused while the tab is hidden), so
routes from a running crawl appear without reloading. Only changed patrols are
fetched. A status line shows when the last patrol was crawled; if the server
cannot be reached it shows `Geen verbinding, opnieuw proberen…` and keeps the
data already on screen. On `/` the selected date, zoom and followed boat are
kept across updates.

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

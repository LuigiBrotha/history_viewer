# uboats

Scraper and API for U-boat data and patrol routes from [uboat.net](https://uboat.net).

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

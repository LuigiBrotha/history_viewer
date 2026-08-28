# Uboat.net Scraper & Route Tracker — Backend Design

## Purpose

Scrape [uboat.net](https://uboat.net) for the German U-boats commissioned into the Kriegsmarine
and the routes ("patrols") they sailed, store the data locally, and expose it through a
read-only API. This is phase 1 of a two-phase project — phase 2 (out of scope here) is a
Leaflet-based frontend with a time slider that shows which boats are on patrol at a given date
and lets a user follow one boat's route. The API surface in this phase is shaped so phase 2 can
be built against it without backend changes.

Project structure and conventions mirror the sibling project `HuizenDI`
(`/home/scout/PycharmProjects/HuizenDI`): FastAPI + `wireup` DI container, async SQLAlchemy on
SQLite, `app/core` / `app/http/api` / `app/services` layout, `RequestHandlerRegistry`
auto-discovery of route handlers, sync `requests` + `selectolax` scrapers driven from an async
orchestrator via `asyncio.to_thread`.

## Site structure (verified by fetching live pages)

- `/boats/listing.html` — a single page listing all ~1153 commissioned U-boats, each linking to
  `/boats/{slug}.htm` (e.g. `/boats/u99.htm`). No pagination.
- `/boats/{slug}.htm` — boat detail: type, builder, laid down/launched/commissioned dates,
  fate, and a link "View the N war patrols" → `/boats/patrols/{slug}.html`.
- `/boats/patrols/{slug}.html` — table of the boat's patrols: number, commander, departure
  date+port, arrival date+port (or a fate like "Sunk"), days at sea, tonnage, and a "View" link
  to `/boats/patrols/patrol_{id}.html`.
- `/boats/patrols/patrol_{id}.html` — one patrol's detail page. Contains, embedded in a
  `<script>` tag driving a Leaflet map:
  - `var patrolRouteCoordinates = [[lat, lng], ...]` — the ordered route polyline.
  - A separate ordered list of dated links (`<a href="/boats/patrols/{slug}/{date}.html">18 Jun
    1940</a>`, one per "daily position") in the same order and count as the coordinate array
    (verified: both were length 11 for the same patrol). Zipping these two ordered lists gives a
    date for each route point **without any extra HTTP requests**.

`robots.txt` disallows several named AI crawlers (including `ClaudeBot`) and sets
`Crawl-delay: 10` for the default rule. Decision: respect the 10s crawl-delay, identify with a
distinct User-Agent, and crawl strictly sequentially (no concurrency) — see Decisions.

## Decisions

| Concern | Decision |
|---|---|
| Crawl politeness | Sequential requests only, minimum 10s between requests to uboat.net (configurable, default 10), distinct User-Agent string. No concurrency — a 10s global delay makes parallel fetches pointless anyway. |
| HTTP/parsing | Sync `requests` + `selectolax`, matching HuizenDI's `DefaultScraper` style. Route coordinates are extracted from the inline `<script>` block with a targeted regex (`patrolRouteCoordinates = \[...\]`), not JS execution — no headless browser needed. |
| Crawl trigger | A standalone, resumable script (`app/crawl.py`), not an HTTP-triggered background task — a full crawl of ~1153 boats plus patrols easily runs many hours at 10s/request, which doesn't belong inside a web request/response cycle or tied to the FastAPI process lifetime. Run manually now (`poetry run python -m app.crawl`); can be wrapped in cron/APScheduler later without redesign, mirroring HuizenDI's own evolution from live per-request scraping toward a scheduled orchestrator. |
| Scoped runs | `app/crawl.py` accepts `--limit N` and `--slugs u99,u100,...` to crawl a subset (used for the initial 10-boat run) and `--force` to re-crawl boats already marked successful. Default (no flags) is a full crawl of the listing. |
| Resumability | A `BoatCrawlState` table records per-boat status/last attempt/last error. A re-run skips boats already marked `success` unless `--force` is passed, so an interrupted multi-hour crawl can be restarted without re-fetching everything. |
| Route dates | `RoutePoint.date` is populated by zipping the ordered daily-position links with the ordered coordinate array on the same patrol page. If the two lists' lengths don't match for a given patrol (seen as a possible edge case, not yet observed), points are stored with `date = NULL` rather than the parse failing. |
| Scope | Only the main "all U-boats" listing (~1153 commissioned boats). Foreign/captured boats and never-commissioned/never-laid-down boats (separate site categories) are excluded. |
| Attack/sinking markers | Not modeled. The patrol map also plots Allied-attack and sinking event markers; only the route itself (the polyline) is captured, per explicit scope — this is a scraper for *routes*, not combat events. |
| Boat lifecycle dates | Parsed defensively into `date | None` via a small shared parser (free-text historical data isn't 100% uniform — e.g. some boats show "Not commissioned"); unparseable values are stored as `NULL`, not raised as errors, so one malformed boat page never aborts the crawl. |
| Contact identification | `PoliteHttpClient`'s User-Agent is built from a `.env`-configurable `CRAWLER_CONTACT` setting (optional, empty by default) — nothing is hardcoded, the user opts in if they want a contact string sent with requests. |

## Data model (`app/services/storage/models.py`)

- **`Boat`** — `id`, `slug` (unique), `number`, `type`, `builder`, `laid_down`, `launched`,
  `commissioned` (nullable dates), `fate` (text), `last_crawled_at`.
- **`Patrol`** — `id`, `boat_id` (FK), `external_id` (from `patrol_{id}` URL, unique),
  `patrol_number`, `commander`, `departure_port`, `departure_date`, `arrival_port`,
  `arrival_date`, `days_at_sea`, `tonnage`, `description`.
- **`RoutePoint`** — `id`, `patrol_id` (FK), `sequence` (int, preserves polyline order), `lat`,
  `lng`, `date` (nullable).
- **`BoatCrawlState`** — `slug` (PK), `status` (`success`/`failed`), `last_attempt_at`,
  `last_success_at`, `last_error` — mirrors HuizenDI's `SiteHealth` pattern, scoped per-boat
  instead of per-site since this is a single-site, many-entity crawl.

## Scraping components (`app/services/scraping/uboat_net/`)

- `http_client.py` — `PoliteHttpClient` wraps `requests.Session`; enforces the shared minimum
  delay between requests and sets the User-Agent from settings.
- `dates.py` — shared `"18 Jun 1940"`-style parser, returns `date | None`, never raises.
- `listing_scraper.py` — fetches `/boats/listing.html`, yields `(slug, number)` for every boat.
- `boat_scraper.py` — fetches `/boats/{slug}.htm`, returns a `BoatData` dataclass.
- `patrol_list_scraper.py` — fetches `/boats/patrols/{slug}.html`, returns
  `list[PatrolSummary]` (includes each patrol's detail URL).
- `patrol_detail_scraper.py` — fetches `/boats/patrols/patrol_{id}.html`, returns a
  `PatrolDetail` dataclass with an ordered `list[RoutePointData]` (lat/lng/date).

## Orchestration (`app/crawl.py`)

An async script, sequential throughout (one HTTP request in flight at a time, `asyncio.sleep`
between each):

```
boats = listing_scraper.fetch()               # one request
boats = apply --limit / --slugs filters
for boat in boats:
    if BoatCrawlState[boat].status == success and not --force:
        continue
    try:
        boat_data = await to_thread(boat_scraper.fetch, boat.slug)
        await BoatRepository.upsert(boat_data)
        patrols = await to_thread(patrol_list_scraper.fetch, boat.slug)
        for patrol_summary in patrols:
            detail = await to_thread(patrol_detail_scraper.fetch, patrol_summary.url)
            await PatrolRepository.upsert(boat.slug, patrol_summary, detail)
        await BoatCrawlStateRepository.record_success(boat.slug)
    except Exception as exc:
        await BoatCrawlStateRepository.record_failure(boat.slug, str(exc))
        continue  # never abort the whole crawl for one boat
```

CLI: `poetry run python -m app.crawl [--limit N] [--slugs u99,u100] [--force] [--delay 10]`.

## Query API (`app/http/api/uboats/`)

Read-only, reads from the DB only — completely decoupled from the crawl script/process:

- `GET /api/uboats/boten` — list boats (`slug`, `number`, `type`, `fate`, patrol count).
- `GET /api/uboats/boten/{slug}` — boat detail plus its patrol summaries.
- `GET /api/uboats/routes` — bulk export for the future frontend: every patrol with its boat's
  `slug`/`number`, `departure_date`, `arrival_date`, and its ordered, dated route points. Sized
  to be loaded once by a client and filtered/interpolated there (a few thousand patrols, tens of
  thousands of points — a few MB of JSON at full scale; trivial at the initial 10-boat scope).

## Testing

- Parser tests against saved real HTML fixtures (`listing.html`, `u99.htm`, `patrols/u99.html`,
  `patrol_4754.html` — already fetched during design and available to copy into
  `tests/fixtures/`).
- `dates.py` unit tests: valid dates, "Unknown"/blank/malformed input → `None`.
- Repository tests (`Boat`, `Patrol`, `RoutePoint`, `BoatCrawlState`) against in-memory SQLite,
  mirroring HuizenDI's `AdRepository`/`SiteHealthRepository` tests.
- `app/crawl.py` orchestration logic tested as a plain async function with fake scraper
  functions substituted in (no real HTTP, no real 10s delays) — asserts upserts happen, a
  raised exception in one boat's scrape is caught and recorded without stopping the loop, and
  `--force`/`--limit`/`--slugs` filter the work list correctly.
- Query endpoint tests against a seeded in-memory DB.
- Manual: run `poetry run python -m app.crawl --limit 10`, confirm 10 boats and their patrols/
  routes land in the DB, then hit the three endpoints and confirm the shapes.

## Out of scope (deferred)

- Attack/sinking event markers from the patrol maps.
- Foreign/captured and never-commissioned/never-laid-down boat categories.
- Scheduling the crawl (cron/APScheduler) — manual invocation only for now.
- The Leaflet frontend (phase 2, separate design once this API has real data behind it).
- Per-domain rate limiting beyond the single global 10s delay (not needed — this project only
  ever talks to one host).

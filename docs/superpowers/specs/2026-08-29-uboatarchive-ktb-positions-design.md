# uboatarchive.net KTB Position Ingestion — Design

**Status:** Approved for planning.

## Goal

Replace the coarse, sparse route points we currently derive from uboat.net with
higher-precision positions transcribed from original war diaries (KTBs, Kriegstagebücher)
published at uboatarchive.net, wherever we can decode and validate them. The user has
explicitly prioritized accuracy over coverage: a patrol we can't confidently decode keeps
its existing uboat.net-derived route, rather than showing an unverified guess.

**Why:** uboat.net's route points are sparse waypoints. uboatarchive.net's KTB
transcriptions log a position roughly every four hours, in the Kriegsmarine's own grid
notation (`Quadratkarte`, e.g. `AK 0334`), giving meaningfully finer resolution — but only
for the subset of boats/patrols the archive has transcribed, and only once that grid
notation is correctly converted to lat/lng.

## Non-goals (deferred)

- Itemized ship-kills data (ship name, date, individual tonnage) from uboat.net's
  "successes" pages — scoped separately, not part of this effort.
- Running the full ~1153-boat uboat.net crawl — still independently deferred from phase 1.
- Any frontend changes — phase 2's frontend already consumes route points generically; a
  denser/more accurate set of points for a patrol requires no frontend code change.

## Architecture Overview

A new scraping module, `app/services/scraping/uboat_archive/`, mirroring the existing
`app/services/scraping/uboat_net/` module's shape (politeness-wrapped HTTP client, HTML
parsing functions, typed dataclasses). It runs as a second, independent crawl pass
(`app/crawl_archive.py`, a new CLI entrypoint alongside the existing `app/crawl.py`) that:

1. Fetches `uboatarchive.net/KTB/KTBList.htm` once — a single comprehensive index of every
   available KTB link on the site.
2. Filters to WWII entries (the site also hosts WWI `SM-`-prefixed boats; out of scope —
   our dataset and uboat.net's are WWII-only).
3. Parses each link's filename for `(boat_number, patrol_number)` — the URL pattern is
   `U-{number}/KTB{number}-{patrol}.htm`, and each such page covers exactly one patrol
   (confirmed by inspecting a page whose site-index blurb suggested multi-patrol coverage —
   it was in fact a single continuous log for one patrol; the index page's summary text is
   not a reliable source of patrol boundaries, only the per-patrol links are).
4. For each boat number found: if no `Boat` row exists with that `number` yet, fetches and
   persists it via the *existing* `fetch_boat`/`fetch_patrol_list` uboat.net functions
   first, so newly-discovered boats get full roster data (type, builder, fate) and a
   canonical patrol list (commander, dates, tonnage) — KTB pages only ever supply
   *positions*, never patrol metadata.
5. For each KTB page: matches it to an existing `Patrol` row by `(boat, patrol_number)`. No
   match → skip and log; we do not fabricate patrol metadata from KTB content.
6. Parses the KTB text for `(date, time, grid_code)` triples, decodes each grid code to
   lat/lng using the calibrated conversion (below), and — only if the patrol ends up with at
   least one successfully decoded point — replaces that patrol's existing route points with
   the KTB-derived ones.

## Grid Conversion

### Notation structure (confirmed from multiple independent sources)

- The globe is divided into 8.1°×8.1° quadrants (486 nautical miles/side; 1° latitude =
  60nm everywhere), each identified by two letters.
- Each quadrant subdivides into a 9×9 grid (first digit pair, 0.9° cells), and each of
  those into a further 9×9 grid (second digit pair, 0.1° cells ≈ 6nm at the equator,
  narrower in longitude at higher latitudes — this matches the documented "varies from the
  equator" caveat exactly, and confirms the grid is degree-regular, not a physical-distance
  projection).
- A grid code's digits reference the cell's **southwest corner** — confirmed by an
  independently-sourced worked example: `AN4116 → 58°57.00'N, 0°48.00'W`.

### Digit decoding (derived and cross-checked, not guessed)

For a 2-digit pair `XY` (X = tens 1–9, Y = ones 1–9, zero never used):

```
row = (X-1)//3*3 + (Y-1)//3   # 0-8, 0 = northmost
col = (X-1)%3*3 + (Y-1)%3     # 0-8, 0 = westmost
```

Derived by directly correlating uboat.net's own `grid_ae.gif` reference image (the "AE"
quadrant, drawn over Iceland's real coastline) against Reykjavík's known coordinates
(64.15°N, 21.94°W) — Reykjavík falls in cell "48", which this formula places at row 5
(6th from north), col 1 (2nd from west) within the quadrant, consistent with Reykjavík's
real position in Iceland's southwest.

Given a quadrant's origin (NW corner: `lat_max`, `lon_min`) and cell size `s` (0.9° at the
first level, 0.1° at the second):

```
cell_lat_sw = lat_max - (row+1)*s
cell_lon_sw = lon_min + col*s
```

Applied twice (first digit pair narrows the 8.1° quadrant to a 0.9° cell; second digit pair
narrows that 0.9° cell to the final 0.1° cell, using the same formula with the first
result's NW corner as the new origin).

### Quadrant-letter origins: calibrated, not hardcoded

We do not hand-transcribe a global letter→origin table from the reference map image — that
risks silent transposition errors, which is exactly what "accurate, not yolo'd" rules out.
Instead:

1. **Adjacency table**: read which letter-pairs are geographically adjacent directly off
   `grid_atlantic.gif` (a much lower-risk visual task than reading precise boundaries) —
   e.g. `AH, AJ, AK, AL, AM, AN, AO` are a contiguous west-to-east row. Stored as a small
   static data file.
2. **Anchor points**: a short fixed list of `(2-letter quadrant, known real-world lat/lng)`
   pairs we can independently verify — `AE` via the Reykjavík derivation above, plus any
   other quadrant we can pin down the same way from the reference images.
3. **Propagation**: every quadrant reachable from an anchor via the adjacency table gets its
   origin computed by simple ±8.1° arithmetic. A quadrant with no path from any anchor is
   left uncalibrated.
4. **Port-anchor validation**: a small fixed table of known U-boat bases/ports with verified
   coordinates (Kiel, Lorient, Brest, St. Nazaire, Danzig/Neufahrwasser, Bergen,
   Wilhelmshaven, Pillau, and — for the Mediterranean/Black Sea, which the reference map
   draws as a visually separate inset and may need its own anchor — Constanza, Sevastopol,
   La Spezia, Toulon). For every KTB grid-code entry that falls within a day of a named-port
   line in the *same* log, decode it and assert the result lands within a sane tolerance
   (e.g. 50km) of that port's known coordinates. This is an automated test using real data,
   not a one-time manual spot-check — it runs against the actual crawled corpus, and any
   quadrant that fails calibration this way is treated as uncalibrated (dropped, not forced).
5. **Regression fixture**: `AN4116 → 58°57.00'N, 0°48.00'W` is baked in as a unit test
   fixture for the decoder, independent of the calibration data.

A patrol whose grid codes all fall in uncalibrated quadrants keeps its existing
uboat.net-derived route points untouched (Non-goal/fallback policy, confirmed with the
user).

## KTB Text Parsing

KTB pages are freeform HTML transcriptions of handwritten logs — dates in `DD.MM.YY`
format, times as `HH.MM`, and grid codes (`[A-Z]{2}\s?\d{4}`) appearing inline amid
narrative text (weather reports, sightings, attacks), not in a clean tabular structure.
Parsing extracts every `(date, time, grid_code)` triple found in the page text, carrying
the most recent date forward for lines that only restate a time. Only grid codes whose
2-letter prefix is calibrated get decoded and kept; the parser does not attempt to validate
narrative content.

## Data Model Changes

- `RoutePoint` gains a nullable `time: Time` column, alongside the existing `date: Date`.
  KTB-derived points populate both; existing uboat.net-derived points keep `time = null`.
  This is additive and backward-compatible — the phase-2 frontend's `time-model.js` already
  operates at day granularity via `date` alone and needs no change.
- A new `ArchiveCrawlState` table (mirroring the existing `BoatCrawlState` pattern) tracks
  per-KTB-page crawl status (`slug`, `patrol_external_id`, `status`, timestamps, last error)
  so re-runs can skip already-processed pages and failures are diagnosable, consistent with
  how the uboat.net crawler already tracks state.
- For a patrol that gets validated KTB points: its existing route points are deleted and
  replaced with the KTB-derived set (full replace, confirmed with the user) — one source of
  truth per patrol, always the most precise available.

## Crawl Politeness

Same discipline as the existing uboat.net crawler: sequential requests only, a mandatory
delay between requests (10s, matching the existing convention), a distinct descriptive
User-Agent. `uboatarchive.net` has no `robots.txt` (checked — 404/empty), which does not
relax this; the same courtesy applies regardless.

## Testing Strategy

- **Grid decoder** (`app/services/scraping/uboat_archive/grid.py` or similar): full unit
  coverage — digit-decode math against the `AN4116` fixture, quadrant-origin propagation
  against the adjacency table, and the Reykjavík/`AE` derivation as a fixture.
- **Port-anchor validation**: an automated check (test or crawl-time assertion) that scans
  the real crawled KTB corpus for grid-codes near named-port mentions and asserts they
  decode within tolerance — this is the primary defense against a subtly wrong calibration
  slipping through.
- **KTB HTML parsing**: fixture-based tests using real saved KTB page HTML (a few pages
  representative of the format, including one with mixed narrative/position lines like the
  U-24 example).
- **Boat/patrol matching and replace logic**: unit tests against the storage layer,
  consistent with phase 1's testing conventions.
- Manual end-to-end verification against a real crawl run, same convention as phases 1–2.

## Open Risk, Explicitly Accepted

Coverage will be partial along two independent axes: which patrols uboatarchive.net has
transcribed at all, and which quadrant letters we can calibrate via the adjacency+anchor
method. Both are handled the same way — fall back to existing data rather than guess. This
is a deliberate accuracy-over-completeness trade-off per the user's explicit instruction.

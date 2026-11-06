# Battle articles and pinnable URLs — Design

Selecting a Veldslag opens its Artikel in a third column: map | battle list | Artikel. The
whole view (date or period, Veldslag, Gevolgde boot, Kaartuitsnede) lives in the URL, so a
moment can be pinned with a bookmark. Domain terms are in `CONTEXT.md`. Why we render
Artikelen ourselves: `docs/adr/0001-artikelen-uit-de-dump-renderen.md`.

Target screens are full HD and 4K. No separate phone design; the phone layout only has to
keep working as it does now.

Two parts, built in this order. Each can go to `master` on its own.

## Part 1: Artikel column

### Data

| Topic | Decision |
|---|---|
| Source | The local dump `~/.cache/uboats/wikipedia/enwiki-*-pages-articles.xml.bz2`, never the live Wikipedia. |
| Extraction | `tools/extract_battles.py` (build on branch `uboat-extract`, which has the resumable version) writes in the same pass: `battles.json` as now, plus the wikitext of every Veldslag and every redirect that points to one, into `uboats.db`. |
| Redirects in one pass | A redirect can come before its target in the dump. All redirects (title → target) go into a scratch table during the pass; at the end only those whose target is a Veldslag are kept and the scratch table is dropped. |
| Tables | `battle_articles(title PK, wikitext, dump_name, extracted_at)`, `battle_redirects(alias PK, title FK)`. Titles in Wikipedia form with spaces; lookup normalises underscores and the first letter. |
| Identity | A Veldslag is identified by its article title. `battles.json` records already carry `url`; the title is derived from it. |

### Backend

| Topic | Decision |
|---|---|
| Endpoint | `GET /api/battles/articles/{title}` → `{title, html, url}`. The title may be a redirect; the response carries the real title. 404 when there is no wikitext. |
| Rendering | Per request, with an in-memory LRU cache. Wikitext → HTML by our own renderer: headings, paragraphs, bold/italic, lists, tables (simple), internal and external links, images with caption, and an infobox built from the `Infobox military conflict` / `military operation` / `battle` fields (date, place, result, belligerents, commanders, strength, casualties). |
| Left out | `<ref>`s and the reference sections, navboxes, "See also", "Further reading", "External links", categories, interlanguage links, hatnotes. Unknown templates are dropped, except a small list rendered as plain text (`convert`, `flag`/`flagicon` name, `lang`, `nowrap`, dates). |
| Sanitising | Output passes a whitelist of tags and attributes on the server: no scripts, styles, event handlers or `javascript:` URLs. The frontend inserts only this cleaned HTML. |
| Links | Every internal link carries `data-title`. When the target (directly or via a redirect) is a Veldslag, it also carries `data-battle` with the real title. |
| Images | Rendered as `/api/battles/images/{file}?width=N`. The backend fetches the scaled image from Wikimedia (URL derived from the file name), stores it under `~/.cache/uboats/wikipedia/images/` and serves it from there afterwards. Courtesy as for the crawlers: distinct User-Agent, no concurrency. When the fetch fails the figure shows its caption only. |
| Attribution | Below each Artikel: "Bron: Engelse Wikipedia, CC BY-SA 4.0" with a link to the original article. |

### Frontend

| Topic | Decision |
|---|---|
| Trigger | Every selection opens the Artikel: a click in the list and a click on a battle square on the map. Also on `/status` and `/heatmap`. |
| Layout | Third column right of the battle list, with its own draggable divider. Width remembered in `localStorage` (a convenience, not view state). Opens only together with the list. |
| Closing | ✕ closes the Artikel; the list stays. The next selection opens it again. |
| Links | A link with `data-battle` selects that Veldslag in the app: Artikel changes, the list scrolls to it, the map shows it. Every other link opens Wikipedia in a new tab. |
| States | Loading text while fetching; on 404 or an error a short message with the Wikipedia link. |
| Existing link | The "Wikipedia" link in each list row stays. |

## Part 2: view state in the URL (Pin)

| Topic | Decision |
|---|---|
| Map page `/` | `?datum=1942-03-14&veldslag=Second_Happy_Time&boot=u99&kaart=48.5,-20.1,5` |
| `/status`, `/heatmap` | `?van=…&tot=…&veldslag=…&kaart=…` (open ends left out). These pages have no Gevolgde boot. |
| Kaartuitsnede | `kaart=lat,lng,zoom`, lat/lng to 4 decimals. |
| Writing | Always `history.replaceState`: the URL stays current, the back button adds no steps. Updates during playback and panning are throttled. |
| Reading | Only the URL restores the view. A bare URL gives the default view; nothing of the view comes from `localStorage`. A `veldslag` that is a redirect resolves to its Veldslag; an unknown one is ignored. |
| Restoring a Veldslag | Opens the Artikel and marks the Veldslag in list and map. The date comes from `datum`, not from the start of the Veldslag. |
| Links between pages | The links to the other map pages carry `veldslag`, `boot` and `kaart`, not the date or period. The link to `/grafiek` carries nothing. |
| Pinning | A bookmark or copied URL. No button and no pin list in the app. |

## Part 3: Winnaar in `battles.json` (extraction only)

Added during the run, so the dump is read only once. The map colouring comes later on its
own branch; this part only stores the data.

| Topic | Decision |
|---|---|
| Field | Each record in `battles.json` gets `winner`: a list of 0, 1 or 2 Kampen. `[]` = unknown; one Kamp = that side won; two Kampen = undecided (inconclusive, stalemate, draw), one per side. |
| Kampen | `as`, `westers`, `sovjet`, `overig`. Same split as the atlas legend, plus a fourth for everything outside the three (China, partisans, …). |
| Country → Kamp | A fixed table in the tool, keyed by the country names the flag templates and links use (`Nazi Germany`, `Empire of Japan`, `Soviet Union`, `United Kingdom`, …). Axis: Germany, Italy, Japan and their allies (Hungary, Romania, Bulgaria, Slovakia, Croatia, Finland, Thailand, Vichy France, Manchukuo). Western: UK, USA, France, the Commonwealth dominions, the governments in exile, Brazil. Soviet: USSR, Mongolia. Anything else known: `overig`. Not in the table: unknown. |
| Side of a column | The Kamp of the first country in `combatant1` / `combatant2` that is in the table. |
| Reading `result` | Strategic before tactical: if the text names a strategic result, only that part counts. "`<X>` victory" where X is a demonym or `Allied`/`Axis`/`Soviet` → that Kamp. "`<X>` defeat" or "`<X>` … failure" → the other column's Kamp. Inconclusive / stalemate / indecisive / draw / ceasefire → both columns' Kampen. Anything else (e.g. "See aftermath", empty) → `[]`. |

## Part 4: Fill the Artikelen for the known Veldslagen only

The 1728 Veldslagen are already known. Reading the whole 25 GB dump again only to find
them takes hours, so a separate tool reads them directly:

| Topic | Decision |
|---|---|
| Sources | The same dump run (20261001), in `~/.cache/uboats/wikipedia/`: `enwiki-20261001-pages-articles-multistream.xml.bz2`, its `-index.txt.bz2` (`offset:page_id:title`), and `enwiki-20261001-redirect.sql.gz`. |
| Articles | For each title in `battles.json`, the index gives the offset of its bz2 stream. Only those streams are decompressed (each holds 100 pages). The page's wikitext goes into `battle_articles`. |
| Redirects | `redirect.sql.gz` rows in namespace 0 whose target is a Veldslag title (underscores) → `rd_from` page ids → alias titles via the index → `battle_redirects`. |
| Winnaar | The same tool fills `winner` in `battles.json` from each stored article's infobox (Part 3). |
| Tool | `poetry run python -m tools.fill_battle_articles [--dir DIR] [--database URL] [--battles FILE]`. It takes minutes, and a rerun replaces everything. The full extraction (`extract_battles`) still stores articles too, for a future complete rebuild. |

## Testing

- Renderer: fixture articles from `tests/fixtures/wikipedia/` (a few real WWII articles), with
  snapshot-like assertions per construct, and a sanitiser test with hostile input.
- Extraction: a tiny hand-made dump with a redirect before and after its target.
- Endpoints: article by title, by redirect, 404; image cache hit and miss (fetch mocked).
- Frontend (node tests): URL encode/decode as pure functions, round trip, unknown and
  malformed values; link classification in the Artikel.

# Battle Articles and Pinnable URLs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Selecting a Veldslag shows its Artikel, rendered from the local Wikipedia dump, in a third column beside the battle list. The whole view of each map page lives in the URL.

**Architecture:** `tools/extract_battles.py` also stores the wikitext of each Veldslag and the redirects to it in `uboats.db`. A FastAPI route renders that wikitext to sanitised HTML with our own renderer (mwparserfromhell + nh3), and a second route serves Wikimedia images from a local disk cache. In the frontend, a new Artikel pane sits in a nested split right of the battle list. A pure `url-state.js` module encodes and decodes the view, and each page writes it with `history.replaceState`.

**Tech Stack:** Python 3.12, FastAPI + wireup class-based handlers, SQLAlchemy (async in the app, sync in the tool), SQLite, `mwparserfromhell`, `nh3`, `requests`; plain ES modules with `node --test`; Leaflet 1.9.4.

**Spec:** `docs/superpowers/specs/2026-11-06-battle-articles-design.md` (also read `docs/adr/0001-artikelen-uit-de-dump-renderen.md` and `CONTEXT.md`).

## Global Constraints

- Branch `uboat-articles`, which must first be rebased onto `uboat-extract` (it holds the resumable extract tool this plan extends). Before Task 1: `git rebase uboat-extract` (only docs commits, no conflicts expected).
- Domain words in code comments, UI text and docs follow `CONTEXT.md`: Veldslag, Artikel, Kaartuitsnede, Pin, Gevolgde boot. UI text is Dutch.
- Articles come only from the dump, never from the live Wikipedia. Only images are fetched live, once, and then cached.
- Every HTML string that reaches the page has passed the server-side whitelist sanitiser. The frontend never builds HTML from article text.
- Wikimedia requests: User-Agent `uboats-scraper/0.1 (+contact: {CRAWLER_CONTACT})` (reuse `app/services/scraping/uboat_net/http_client.py`'s builder), one request at a time, timeout 20 s.
- Attribution under each Artikel: `Bron: Engelse Wikipedia, CC BY-SA 4.0`, with a link to the original article.
- URL parameters: `datum`, `van`, `tot`, `veldslag`, `boot`, `kaart` (`lat,lng,zoom`, lat/lng with 4 decimals). Always `history.replaceState`, never `pushState`. A bare URL gives the default view; view state never comes from `localStorage`.
- Target screens are full HD and 4K. The phone layout (≤ 699 px) only has to keep working: there the Artikel pane is simply not shown.
- Tests: `poetry run pytest` and `cd frontend && node --test tests/`, both green after every task.

## Review Focus

1. **A Veldslag title with characters that need escaping in a URL** (`Battle of Crete`, `Operation "Weserübung"`, `Battle of the Bulge (1944–45)`). The URL round trip and the API path must both keep the title intact → tests in Task 8 and Task 4.
2. **An article whose wikitext has unbalanced templates or tags**, which is common in the dump. The renderer must return partial HTML, never a 500 → test in Task 3.
3. **A redirect chain or a redirect to a non-Veldslag.** The lookup resolves exactly one hop to a Veldslag and otherwise returns not found, without looping → test in Task 2.
4. **An image that Wikimedia does not serve** (404, fair-use file only on en.wikipedia, a timeout). The endpoint answers 404 quickly, does not cache the failure as an image, and the figure shows only its caption → test in Task 5.
5. **A URL with stale or malformed values** (`datum=1950-01-01`, `kaart=abc`, `boot=unknown`, `veldslag` removed in a new extract). Each bad value is ignored on its own, and the rest of the view is still restored → tests in Task 8 and Task 9.

---

## File structure

| File | Responsibility |
|---|---|
| `app/services/storage/models.py` (modify) | `BattleArticle`, `BattleRedirect` tables |
| `tools/extract_battles.py` (modify) | also write wikitext and redirects to the database |
| `app/services/wiki/titles.py` (create) | `normalize_title` |
| `app/services/storage/battle_article_repository.py` (create) | lookup by title or redirect; the set of battle titles |
| `app/services/wiki/render.py` (create) | wikitext → HTML |
| `app/services/wiki/infobox.py` (create) | infobox fields → HTML table |
| `app/services/wiki/sanitize.py` (create) | nh3 whitelist |
| `app/services/wiki/article_service.py` (create) | injectable: repository + renderer + LRU |
| `app/services/wiki/image_cache.py` (create) | Wikimedia thumbnail URL, fetch, disk cache |
| `app/http/api/battles/article.py` (create) | `GET /api/battles/articles/{title}` |
| `app/http/api/battles/image.py` (create) | `GET /api/battles/images/{file}` |
| `frontend/js/battle-article.js` (create) | Artikel pane: load, show, ✕, link clicks |
| `frontend/js/battle-split.js` (modify) | reusable for a second split (key, sizes) |
| `frontend/js/battles.js` (modify) | open the Artikel on every selection; `selectBattle`, `selectedBattle`, `onBattleChange` |
| `frontend/js/url-state.js` (create) | pure encode/decode of the view |
| `frontend/js/url-sync.js` (create) | throttled `replaceState`, rewriting the nav links |
| `frontend/js/main.js`, `status.js`, `heatmap.js`, `period-slider.js` (modify) | restore and report the view |
| `frontend/index.html`, `status.html`, `heatmap.html`, `css/style.css` (modify) | Artikel column markup and styles |

---

## Part 1: Artikel column

### Task 1: Store wikitext and redirects during extraction

**Files:**
- Modify: `app/services/storage/models.py`, `tools/extract_battles.py`, `frontend/battles/README.md`, `pyproject.toml` (no new deps here)
- Test: `tests/tools/test_extract_battles.py`

**Interfaces:**
- Produces (models.py):
  - `class BattleArticle(Base)`, `__tablename__ = "battle_articles"`: `title: str` PK, `wikitext: str`, `dump_name: str`, `extracted_at: datetime`
  - `class BattleRedirect(Base)`, `__tablename__ = "battle_redirects"`: `alias: str` PK, `title: str` (FK `battle_articles.title`)
- Produces (tool): `run(dump, output, save_every_seconds=…, database_url="sqlite:///uboats.db")`; CLI flag `--database` (default `sqlite:///./uboats.db`). Titles are stored exactly as in the dump (spaces, original case).

- [ ] **Step 1: Write the failing tests** in `tests/tools/test_extract_battles.py`, using a tiny hand-made `.xml.bz2` dump written in `tmp_path` (helper `write_dump(path, pages)` building `<page><title>…</title><ns>0</ns>[<redirect title="…"/>]<revision><text>…</text></revision></page>`), with two battle articles from `tests/fixtures/wikipedia/battle_pages.json` (`Second Happy Time`, `Battle of Midway`):
  - `test_run_stores_wikitext_of_each_battle`: after `run(...)`, `battle_articles` has exactly those two titles, and `wikitext` equals the fixture text.
  - `test_run_keeps_redirects_to_battles_before_and_after_target`: the redirect `Operation Drumbeat → Second Happy Time` placed **before** the target page and `Midway → Battle of Midway` placed **after** it both end up in `battle_redirects`. `Some redirect → Paris` does not.
  - `test_run_drops_redirect_scratch_table`: after the run, `sqlite_master` has no table `battle_redirects_scratch`.
  - `test_rerun_replaces_rows`: running twice gives the same row counts (no duplicates).
- [ ] **Step 2: Run** `poetry run pytest tests/tools/test_extract_battles.py -v`. Expected: the new tests FAIL (unexpected keyword `database_url`).
- [ ] **Step 3: Implement.**
  - Add the two models.
  - The tool opens `sqlalchemy.create_engine(database_url)` and creates only these tables (plus a plain `battle_redirects_scratch(alias TEXT PRIMARY KEY, target TEXT)`).
  - In the page loop, a redirect page in ns 0 is recognised by a byte search for `b"<redirect"` before XML parsing, so that redirects skip the `CANDIDATE` filter. Its `alias → target` is upserted into the scratch table.
  - An accepted battle upserts its `BattleArticle`.
  - Commit at the same moments as `save()`, so a resumed run stays consistent.
  - At the end, copy `INSERT OR REPLACE INTO battle_redirects SELECT alias, target FROM battle_redirects_scratch WHERE target IN (SELECT title FROM battle_articles)`, then drop the scratch table. Delete `battle_articles` rows whose title is no longer in `battles` before that.
  - Extend `iter_candidate_pages` into an iterator that yields both kinds, e.g. `(number, title, text, redirect_target_or_None)`.
- [ ] **Step 4: Run** `poetry run pytest tests/tools -v`. Expected: all PASS, including the existing extract tests.
- [ ] **Step 5:** Add a paragraph to `frontend/battles/README.md`: the run also fills `battle_articles`/`battle_redirects` in `uboats.db` (`--database` to choose another). **Commit:** `Store each battle's wikitext and the redirects to it while extracting`.

### Task 2: Title normalisation and article repository

**Files:**
- Create: `app/services/wiki/__init__.py`, `app/services/wiki/titles.py`, `app/services/storage/battle_article_repository.py`
- Test: `tests/services/wiki/test_titles.py`, `tests/services/storage/test_battle_article_repository.py`

**Interfaces:**
- Consumes: the Task 1 models.
- Produces:
  - `normalize_title(raw: str) -> str`: URL-decode, `_` → space, collapse whitespace, strip, drop a `#fragment`, capitalise the first character only.
  - `class BattleArticleRepository(session: AsyncSession)`:
    - `async get(title: str) -> tuple[str, str] | None`: `(real_title, wikitext)`. Tries the normalised title, then one redirect hop.
    - `async battle_index() -> dict[str, str]`: normalised title or alias → real title, for every article and redirect.

- [ ] **Step 1: Write the failing tests.**
  - `normalize_title`: `"second_Happy_Time" → "Second Happy Time"`, `"Battle%20of%20Crete" → "Battle of Crete"`, `"Battle of Midway#Background" → "Battle of Midway"`, `"  Operation  Torch " → "Operation Torch"`, `"Battle of the Bulge (1944–45)"` unchanged.
  - Repository (on a `tmp_path` db created with `init_models`): `get("Second_Happy_Time")` → the real title; `get("Operation Drumbeat")` → `("Second Happy Time", …)`; `get("Unknown")` → `None`; a redirect whose `title` is not in `battle_articles` → `None`; `battle_index()` contains both the article and the alias.
- [ ] **Step 2: Run** `poetry run pytest tests/services/wiki tests/services/storage/test_battle_article_repository.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement** both files. `init_models` already creates the new tables through `Base.metadata.create_all`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit:** `Look up a battle article by its title or a redirect`.

### Task 3: Wikitext renderer, infobox and sanitiser

**Files:**
- Modify: `pyproject.toml` (add `mwparserfromhell = "^0.6.6"`, `nh3 = "^0.2.21"`, then `poetry lock && poetry install`)
- Create: `app/services/wiki/render.py`, `app/services/wiki/infobox.py`, `app/services/wiki/sanitize.py`
- Test: `tests/services/wiki/test_render.py`, `tests/services/wiki/test_sanitize.py`

**Interfaces:**
- Produces:
  - `render_article(wikitext: str, *, battle_index: Mapping[str, str], image_src: Callable[[str, int], str]) -> str`: sanitised HTML. `image_src(file_name, width)` returns the `src` for an image.
  - `render_infobox(fields: Mapping[str, str], render_inline: Callable[[str], str]) -> str`: a `<table class="article-infobox">`.
  - `sanitize(html: str) -> str`

**What the renderer outputs** (the tests pin each one):

| Wikitext | HTML |
|---|---|
| `== H ==` / `=== H ===` | `<h3>` / `<h4>` (`<h2>` is reserved for the Artikel title in the pane) |
| paragraphs (blank line) | `<p>` |
| `''x''`, `'''x'''` | `<i>`, `<b>` |
| `* a` / `# a` | `<ul><li>` / `<ol><li>` |
| `[[Target|label]]` | `<a href="https://en.wikipedia.org/wiki/Target" data-title="Target">label</a>`, plus `data-battle="<real title>"` when `normalize_title(Target)` is in `battle_index` |
| `[http://x label]` | `<a href="http://x">label</a>` |
| `[[File:X.jpg|thumb|caption]]` / `[[Image:…]]` | `<figure><img src="{image_src('X.jpg', 330)}" alt="caption" loading="lazy"><figcaption>caption</figcaption></figure>` |
| `{{Infobox military conflict|…}}` (also `military operation`, `battle`) | `render_infobox`, rendered first. `image` field → a figure at width 330. Rows in this order and with these labels: `date` Datum, `place`/`location` Plaats, `result` Resultaat, `territory` Gebied, `combatant1`/`combatant2` Strijdende partijen, `commander1`/`commander2` Bevelhebbers, `strength1`/`strength2` Sterkte, `casualties1`/`casualties2` Verliezen. Sides 1 and 2 go side by side in two cells. Empty rows are left out. |
| `{{convert|5|km}}` | `5 km` |
| `{{flag|Germany}}`, `{{flagicon|…}}`, `{{flagcountry|…}}` | the country name / nothing |
| `{{lang|de|Text}}`, `{{nowrap|x}}`, `{{small|x}}` | `x` |
| `{{start date|1942|1|14}}`, `{{end date|…}}` | `14 January 1942` (reuse `render_date` from the tool by moving it to `app/services/wiki/titles.py`'s sibling `dates.py` if importing from `tools` is awkward) |
| any other template, `<ref>…</ref>`, `<!-- -->`, `[[Category:…]]`, interlanguage links | nothing |
| sections `References`, `Notes`, `Citations`, `Bibliography`, `Sources`, `Further reading`, `External links`, `See also`, `Footnotes` | section and everything below it until the next heading of the same or a higher level dropped |
| bare `<br>`, `<sup>`, `<sub>`, `<blockquote>` | kept (whitelist) |
| simple `{| … |}` tables | `<table class="article-table">` with `<tr><th>/<td>`; cell attributes dropped |

`sanitize`: nh3 with tags `{a, b, i, em, strong, p, br, h3, h4, ul, ol, li, figure, figcaption, img, table, thead, tbody, tr, th, td, sup, sub, blockquote, span}`. Attributes: `a: href, data-title, data-battle, class`; `img: src, alt, loading, width`; `table/td/th/span: class, colspan, rowspan`. URL schemes `http`, `https`, plus relative paths (for `/api/battles/images/…`).

- [ ] **Step 1: Write the failing tests**, one per row of the table above (small inline wikitext), plus:
  - `test_renders_second_happy_time_fixture`: render the fixture text of `Second Happy Time`. The result contains `class="article-infobox"`, at least 3 `<h3>`, no `{{`, no `<ref`, no `References`.
  - `test_unbalanced_markup_renders_partially` (Review Focus 2): `"Intro ''open {{Infobox military conflict|date=1942\n\n== H ==\ntext"` returns a string containing `text` and raises nothing.
  - `test_sanitize_strips_hostile_input`: `<script>`, `onerror=`, `style=`, `javascript:` hrefs and `<iframe>` are all gone; `data-battle` on `<a>` survives.
  - `test_link_to_battle_redirect_gets_real_title`: `[[Operation Drumbeat]]` with `battle_index={"Operation Drumbeat": "Second Happy Time"}` → `data-battle="Second Happy Time"`.
- [ ] **Step 2: Run** `poetry run pytest tests/services/wiki -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Parse with `mwparserfromhell.parse`. Walk nodes (`Text`, `Wikilink`, `ExternalLink`, `Template`, `Tag`, `Heading`, `Comment`) and build HTML with `html.escape` on every text and attribute value. Split into blocks on blank lines and list/heading line starts. `render_article` calls `sanitize` on its result. Wrap the node walk per block in `try/except Exception` and fall back to the block's escaped `strip_code()` text, so one bad block never loses the article.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit:** `Render a battle's wikitext to sanitised HTML with its own infobox`.

### Task 4: Article endpoint

**Files:**
- Create: `app/services/wiki/article_service.py`, `app/http/api/battles/__init__.py`, `app/http/api/battles/article.py`
- Test: `tests/http/api/test_battle_article.py`

**Interfaces:**
- Consumes: `BattleArticleRepository` (Task 2), `render_article` (Task 3), `image_url_for(file_name: str, width: int) -> str` (Task 5 defines it; until then use `lambda f, w: f"/api/battles/images/{quote(f)}?width={w}"` — Task 5 moves exactly that into `image_cache.py`).
- Produces:
  - `@injectable class ArticleService(session_factory)`: `async article(title: str) -> ArticleOut | None`. An LRU of 64 rendered articles keyed by the real title; the battle index is loaded once and reloaded when it is empty.
  - `@dataclass ArticleOut`: `title: str`, `html: str`, `url: str` (`wiki_url(title)` from the tool, moved to `titles.py`).
  - Route `GET /api/battles/articles/{title:path}`, name `battles_article` → `ArticleOut`, 404 `{"detail": "Geen artikel voor deze veldslag."}`.

- [ ] **Step 1: Write the failing tests** (same style as `tests/http/api/test_status.py`, calling `RequestHandler(...).handle_request(...)` directly):
  - Found by exact title; found via redirect (`title` in the response is the real one); `HTTPException` 404 for an unknown title.
  - `test_title_with_special_characters` (Review Focus 1): store `Operation "Weserübung"` and `Battle of the Bulge (1944–45)`, and request them with `quote(title)`.
  - `test_second_request_is_served_from_cache`: patch `render_article` with a counter; two requests → one call.
- [ ] **Step 2: Run** `poetry run pytest tests/http/api/test_battle_article.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** The `{title:path}` converter keeps slashes inside titles; normalise inside the service.
- [ ] **Step 4: Run** the full suite `poetry run pytest`. Expected: PASS (the registry picks up the new handler automatically).
- [ ] **Step 5: Commit:** `Serve a battle's article from the extracted wikitext`.

### Task 5: Image cache endpoint

**Files:**
- Create: `app/services/wiki/image_cache.py`, `app/http/api/battles/image.py`
- Modify: `app/core/config.py` (`WIKI_IMAGE_DIR: str = "~/.cache/uboats/wikipedia/images"`), `app/services/wiki/article_service.py` (use `image_url_for`)
- Test: `tests/services/wiki/test_image_cache.py`, `tests/http/api/test_battle_image.py`

**Interfaces:**
- Produces:
  - `ALLOWED_WIDTHS = (330, 500, 960)`; any other `width` snaps to the next allowed width up, capped at 960.
  - `image_url_for(file_name: str, width: int) -> str` → `/api/battles/images/{quote(name)}?width={w}`, with `name` the file name using underscores.
  - `thumbnail_urls(file_name: str, width: int) -> list[str]`: the commons URL first, then the en URL. For `md5 = hashlib.md5(name.encode()).hexdigest()`: `https://upload.wikimedia.org/wikipedia/{repo}/thumb/{md5[0]}/{md5[:2]}/{name}/{width}px-{name}`, with a `.png` suffix appended for `.svg` files.
  - `@injectable class ImageCache`: `async get(file_name: str, width: int) -> Path | None`. Disk path `{dir}/{width}/{md5[:2]}/{name}`. On a miss it fetches in a thread (`asyncio.to_thread`), behind an `asyncio.Lock` (one request at a time), and writes atomically. A failure is remembered in memory for 1 hour and nothing is written to disk.
  - Route `GET /api/battles/images/{file_name:path}?width=330` → `FileResponse` with `Cache-Control: max-age=31536000, immutable` (overrides the global `no-cache` for this response), 404 when `get` returns `None`. Only file names ending in `.jpg .jpeg .png .gif .svg .tif .tiff .webp` (case-insensitive) are accepted; anything else is a 404 without a fetch.
- [ ] **Step 1: Write the failing tests:**
  - `thumbnail_urls("Bundesarchiv Bild 101II.jpg", 330)[0] == "https://upload.wikimedia.org/wikipedia/commons/thumb/<md5[0]>/<md5[:2]>/Bundesarchiv_Bild_101II.jpg/330px-Bundesarchiv_Bild_101II.jpg"`, with the md5 computed in the test.
  - Width snapping: `200 → 330`, `400 → 500`, `5000 → 960`.
  - With an injected fake fetch: the first `get` fetches and writes; the second reads from disk without fetching. The commons 404 → en fallback is used.
  - Review Focus 4: both URLs 404 → `None`, nothing on disk, and a second `get` within the hour does not fetch again. A timeout behaves the same.
  - Route: `../../etc/passwd` and `x.html` → 404 without a fetch.
- [ ] **Step 2: Run** `poetry run pytest tests/services/wiki/test_image_cache.py tests/http/api/test_battle_image.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** The fetch function is a constructor parameter (default: a `requests.Session` with the project User-Agent and a 20 s timeout), so tests can inject it. The cache key path is built from the md5 and the sanitised name, never from the raw path segment.
- [ ] **Step 4: Run** `poetry run pytest`. Expected: PASS.
- [ ] **Step 5: Commit:** `Cache the Wikimedia images that battle articles show`.

### Task 6: Artikel pane and its split

**Files:**
- Create: `frontend/js/battle-article.js`
- Modify: `frontend/js/battle-split.js`, `frontend/js/api.js`, `frontend/index.html`, `frontend/status.html`, `frontend/heatmap.html`, `frontend/css/style.css`
- Test: `frontend/tests/battle-article.test.js`, `frontend/tests/battle-split.test.js`

**Interfaces:**
- Produces:
  - `api.js`: `fetchArticle(title: string): Promise<{title, html, url} | null>`. `null` on 404, an `Error` on anything else. 30 s timeout.
  - `battle-split.js`: `initBattleSplit({ ..., storageKey = "uboats.battlePane", defaultWidth = 360 })`. The article split uses `storageKey: "uboats.articlePane"`, `defaultWidth: 520`. Its `open()`/`close()`/`isOpen()` stay as they are. The article split does not persist `open`: it always starts closed (the URL decides).
  - `createArticlePane({ rootEl, load = fetchArticle, onBattleLink, onClose })` → `{ show(battle): Promise<void>, clear() }`.
    - `show` sets the title (`<h2>` with `battle.title`), a `Laden…` line, then the HTML via `template.innerHTML` + `replaceChildren(template.content)` (already sanitised by the server).
    - A footer `<p class="article-source">Bron: Engelse Wikipedia, CC BY-SA 4.0 · <a href=url target=_blank rel="noopener noreferrer">Origineel artikel</a></p>`.
    - On `null`: `Geen artikel beschikbaar voor deze veldslag.` plus the Wikipedia link. On an error: `Artikel kon niet worden geladen.` plus the link.
    - If a later `show` starts before an earlier one finishes, the earlier result is dropped.
  - Clicks inside the article: `a[data-battle]` → `preventDefault`, `onBattleLink(title)`. Any other `a` gets `target="_blank" rel="noopener noreferrer"` (set once after insertion).
  - The ✕ button (`aria-label="Sluit artikel"`) → `onClose()`.
- Markup in all three pages: inside `#battle-pane`'s parent, after `#battle-pane`, add `<div id="article-divider" role="separator" aria-orientation="vertical" aria-label="Formaat van het artikel" aria-controls="article-pane" tabindex="0"></div><article id="article-pane" aria-label="Artikel"></article>`. Wrap list + divider + Artikel so the existing `#battle-pane` width keeps sizing the list only. CSS: Artikel column `flex: 0 0 var(--article-pane-size, 520px)`; readable typography (max line length, infobox floated right inside the column at 4K, figure images `max-width: 100%`); hidden on `max-width: 699px`.

- [ ] **Step 1: Write the failing tests** with the fake DOM from `tests/battle-dom.js` (extend it with `innerHTML` on a `template` stand-in if needed):
  - `show` renders the title and calls `load` with `battle.title`; `null` → the no-article text plus a link with `battle.url`; a rejection → the error text.
  - A stale response is ignored: two `show`s whose first promise resolves last.
  - A click on an anchor with `data-battle="Second Happy Time"` calls `onBattleLink("Second Happy Time")` and prevents the default; an ordinary link gets `target=_blank`.
  - ✕ calls `onClose`.
  - `battle-split`: with `storageKey: "uboats.articlePane"`, the width is saved under that key and the list's key is untouched.
- [ ] **Step 2: Run** `cd frontend && node --test tests/`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Commit:** `Add a resizable column that shows a battle's article`.

### Task 7: Open the Artikel on every selection

**Files:**
- Modify: `frontend/js/battles.js`
- Test: `frontend/tests/battles.test.js`

**Interfaces:**
- Consumes: Task 6.
- Produces: `initBattles(...)` takes the extra option `onBattleChange = (title|null) => {}` and returns, besides `setDate`/`setPeriod`:
  - `selectBattle(title: string, { pickDate = false } = {}): boolean`. Finds the Veldslag by exact title (the server resolves redirects for links; the URL carries the real title). If found, it opens the list split, marks it in list and map (`layer.setSelected`, `layer.showBattle`, `pane.reveal`) and shows the Artikel. Returns false if the title is unknown. When the battles have not loaded yet, the request is kept and applied after loading.
  - `selectedBattle(): string | null`.
- Behaviour:
  - A click in the list does `onPickDate` (date mode) and `selectBattle`.
  - A click on a map square does `selectBattle` without `onPickDate`, as now.
  - `onBattleLink(title)` from the Artikel does the same as a list click.
  - ✕ closes the article split, sets the selection to `null` and calls `onBattleChange(null)`.
  - Every selection calls `onBattleChange(title)`.

- [ ] **Step 1: Write the failing tests** in `battles.test.js` (extend `setup` with an `article-pane`/`article-divider` element and a fake `loadArticle`):
  - A list click shows the Artikel and calls `onBattleChange("Battle of Kursk")`.
  - A map-square click shows the Artikel too.
  - After ✕, `selectedBattle()` is `null`, and the next list click opens the Artikel again.
  - `selectBattle("Midway")` before loading resolves → applied once loaded; `selectBattle("Nope")` after loading → `false`, nothing changes.
  - An Artikel link to `"Atlantic"` selects that Veldslag.
- [ ] **Step 2: Run** `cd frontend && node --test tests/battles.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement.** Pass `loadArticle` through as an option of `initBattles` (default `fetchArticle`) so that tests can inject it.
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Manual check.** `poetry run uvicorn app.main:app --reload`. On `/`, `/status` and `/heatmap`, clicking a Veldslag shows its Artikel with the infobox and images, the ✕ closes it, and a link to another Veldslag switches to it. This needs a filled `battle_articles` table: run Task 1's tool on the real dump (hours), or for a quick check `poetry run python -m tools.extract_battles tests/fixtures/…` with a small dump built from the fixture.
- [ ] **Step 6: Commit:** `Show a battle's article whenever it is selected`.

---

## Part 2: view in the URL (Pin)

### Task 8: Encode and decode the view

**Files:**
- Create: `frontend/js/url-state.js`
- Test: `frontend/tests/url-state.test.js`

**Interfaces:**
- Produces:
  - `readView(search: string, kind: "date" | "period"): View`, where `View = { date?: string, from?: string, to?: string, battle?: string, boat?: string, map?: { lat: number, lng: number, zoom: number } }`. Each field is present only when it is valid.
  - `writeView(view: View, kind): string`: the search string, starting with `?`, or `""` for an empty view. Parameter order: `datum`/`van`,`tot`, `veldslag`, `boot`, `kaart`.
  - `carriedView(view: View): View`: only `battle`, `boat`, `map` (for links to other pages).
- Validation:
  - Dates match `^\d{4}-\d{2}-\d{2}$` and are real dates (the page clamps them to its own range later).
  - `kaart` is three finite numbers with lat in [-90, 90], lng in [-180, 180], zoom an integer in [1, 18].
  - `boot` matches `^[a-z0-9-]+$`.
  - `veldslag` is any non-empty string; spaces are written as `_`, everything else via `URLSearchParams` encoding.
  - lat/lng are written with 4 decimals.

- [ ] **Step 1: Write the failing tests:**
  - Round trip for `{date:"1942-03-14", battle:"Second Happy Time", boat:"u99", map:{lat:48.5,lng:-20.1,zoom:5}}` gives exactly `?datum=1942-03-14&veldslag=Second_Happy_Time&boot=u99&kaart=48.5000,-20.1000,5`.
  - Review Focus 1: titles `Operation "Weserübung"`, `Battle of the Bulge (1944–45)` and `Convoy HX 79 & SC 7` survive the round trip.
  - Review Focus 5: `kaart=abc`, `kaart=91,0,5`, `datum=1942-02-30`, `boot=U 99` and `van=x` are each dropped while the other fields stay.
  - `kind: "period"` reads `van`/`tot` and ignores `datum`.
  - `carriedView` drops `date`/`from`/`to`.
- [ ] **Step 2: Run** `cd frontend && node --test tests/url-state.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit:** `Encode a page's view in its URL`.

### Task 9: Keep the URL in step on the map page

**Files:**
- Create: `frontend/js/url-sync.js`
- Modify: `frontend/js/main.js`, `frontend/index.html` (nav links get `data-carry`)
- Test: `frontend/tests/url-sync.test.js`

**Interfaces:**
- Consumes: Task 8, `battles.selectBattle` / `onBattleChange` (Task 7), `timeline.setDate` (exists), `followBoat` in `main.js`.
- Produces: `createUrlSync({ kind, win = window, doc = document, delayMs = 250 })` → `{ update(partial: View) }`. It merges `partial` (a `null` value deletes the field) into its current view and calls `win.history.replaceState(null, "", pathname + writeView(view, kind))` at most once per `delayMs` (trailing call guaranteed). On every write it also sets the `href` of each `a[data-carry]` to its own path + `writeView(carriedView(view), kindOf(link))`. `data-carry="date"|"period"` gives the target page's kind; links without it (`grafiek`) stay untouched.
- Restore order in `main.js`, once the first routes have arrived and the map exists:
  1. `readView(location.search, "date")`.
  2. `boot`: if it is in `routesBySlug`, `followBoat(slug)` without opening the boat panel.
  3. `datum`: `timeline.setDate(parseDate(date))`, clamped by the timeline itself.
  4. `veldslag`: `battles.selectBattle(title)` (no `pickDate`).
  5. `kaart`: `map.setView([lat, lng], zoom)` last, and the follow fit for this one render is suppressed, so the pinned Kaartuitsnede wins.
- Reporting: `render(date)` → `update({date})`; `followBoat`/reset → `update({boat: slug|null})`; `onBattleChange` → `update({battle})`; `map.on("moveend")` → `update({map})`.

- [ ] **Step 1: Write the failing tests** for `url-sync.js` with a fake `win` (history spy, fake timers via `mock.timers` from `node:test`):
  - Ten `update`s within 250 ms → one `replaceState` with the last view.
  - `update({battle: null})` removes `veldslag`.
  - `a[data-carry="period"]` gets `status?veldslag=…&kaart=…` without `datum`, and a link without `data-carry` is unchanged.
  - Never `pushState` (the spy throws).
- [ ] **Step 2: Run** `cd frontend && node --test tests/url-sync.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement** `url-sync.js`, then wire `main.js` as described. In `index.html`, nav links `status` and `heatmap` get `data-carry="period"`.
- [ ] **Step 4: Run** `cd frontend && node --test tests/`. Expected: PASS.
- [ ] **Step 5: Manual check (Review Focus 5).**
  - Open `/?datum=1942-03-14&veldslag=Second_Happy_Time&boot=u123&kaart=38.0,-72.0,6`: the date, the Artikel, the Gevolgde boot and the exact map position are all restored.
  - Reload during playback: the URL holds the current date.
  - `/?datum=1950-01-01&kaart=abc&boot=nope` opens without errors and with the date clamped.
  - The back button leaves the page.
- [ ] **Step 6: Commit:** `Keep the map page's view in its URL`.

### Task 10: Keep the URL in step on `/status` and `/heatmap`

**Files:**
- Modify: `frontend/js/period-slider.js`, `frontend/js/status.js`, `frontend/js/heatmap.js`, `frontend/status.html`, `frontend/heatmap.html`
- Test: `frontend/tests/period-slider.test.js`

**Interfaces:**
- Consumes: Tasks 7–9.
- Produces: `initPeriodSlider(...)` returns besides `setBounds` also `setPeriod(from: string|null, to: string|null)`. It clamps the values to the bounds, keeps `from ≤ to` (swaps them otherwise), renders and calls `onChange` once. Called before `setBounds`, the period is kept and applied when the bounds arrive.
- Restore in `status.js`/`heatmap.js` with `readView(location.search, "period")`: `van`/`tot` → `slider.setPeriod`, `veldslag` → `battles.selectBattle`, `kaart` → `map.setView` (after the first data, so a later fit doesn't override it). Report: slider `onChange` → `update({from, to})` (a period equal to the full bounds is written as `null`/`null`), `onBattleChange` → `update({battle})`, `moveend` → `update({map})`. Nav links: `./` gets `data-carry="date"`, the other map page `data-carry="period"`, `grafiek` nothing.

- [ ] **Step 1: Write the failing tests:**
  - `setPeriod("1941-01-01", "1942-01-01")` after `setBounds` moves the handles and calls `onChange` once with those dates.
  - Before `setBounds` it is applied when bounds arrive.
  - Out-of-range values are clamped.
  - A reversed pair is swapped.
- [ ] **Step 2: Run** `cd frontend && node --test tests/period-slider.test.js`. Expected: FAIL.
- [ ] **Step 3: Implement** `setPeriod`, then wire both pages.
- [ ] **Step 4: Run** `cd frontend && node --test tests/` and `poetry run pytest`. Expected: both PASS.
- [ ] **Step 5: Manual check.**
  - `/status?van=1941-01-01&tot=1941-12-31&veldslag=Second_Happy_Time&kaart=40,-40,4` restores the period, the Artikel and the Kaartuitsnede. The same works on `/heatmap`.
  - The "Tijdlijn" link carries `veldslag` and `kaart` but no `van`/`tot`.
- [ ] **Step 6:** Update `README.md`:
  - the Artikel column;
  - the URL parameters and that a bookmark is a Pin;
  - that the extract run fills the articles;
  - the image cache folder.
- [ ] **Step 7: Commit:** `Keep the period pages' view in their URL`.

---

## Part 3: Winnaar in `battles.json`

### Task 11: Store each Veldslag's Winnaar while extracting

**Files:**
- Create: `tools/battle_winner.py` (country table, `result` parsing)
- Modify: `tools/extract_battles.py` (`extract_battle` adds `winner`), `frontend/battles/README.md`
- Test: `tests/tools/test_battle_winner.py`, `tests/tools/test_extract_battles.py`

**Interfaces:**
- Produces:
  - `KAMPEN = ("as", "westers", "sovjet", "overig")`
  - `side_kamp(field: str) -> str | None`: the Kamp of the first known country in a combatant field. Countries come from `flag`/`flagcountry`/`flagicon`/`navy`/`army`/`air force` templates (first argument; a `name=` argument does not change the country) and from `[[links]]`.
  - `winner(fields: Mapping[str, str]) -> list[str]`: from `result`, `combatant1`, `combatant2`, following the spec's Part 3 rules.
  - Each battle record gets `"winner": [...]`. The frontend ignores the field for now.

- [ ] **Step 1: Write the failing tests** (`test_battle_winner.py`), using these fields from the fixture infoboxes:
  - Kursk `"Soviet victory"` → `["sovjet"]`; Midway `"American victory"` → `["westers"]`; Convoy HX 79 `"German victory"` with `{{navy|Nazi Germany}}` → `["as"]`; Atlantic `"Allied victory"` → `["westers"]`; Pearl Harbor `"Japanese victory"` → `["as"]`.
  - `"Axis strategic failure"` with combatant1 Nazi Germany and combatant2 Soviet Union → `["sovjet"]`.
  - `"Tactical Japanese victory, strategic Allied victory"` → `["westers"]`.
  - `"Inconclusive"` with Nazi Germany against United Kingdom → `["as", "westers"]`.
  - `"See aftermath"` → `[]`; empty → `[]`.
  - `"Chinese victory"` → `["overig"]`.
  - `side_kamp("{{ubl|{{flagcountry|Nazi Germany}}|{{flagcountry|Kingdom of Italy}}}}") == "as"`; `side_kamp("[[French Third Republic|France]]") == "westers"`; `side_kamp("{{flag|Nazi Germany|name=German Reich}}") == "as"`.
  - In `test_extract_battles.py`: the extracted Kursk record has `"winner": ["sovjet"]`.
- [ ] **Step 2: Run** `poetry run pytest tests/tools -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** Demonyms map to countries in the same table, for example `German` → Nazi Germany and `American` → United States. Match case-insensitively on whole words.
- [ ] **Step 4: Run** `poetry run pytest`. Expected: PASS.
- [ ] **Step 5:** Add a line about `winner` to `frontend/battles/README.md`. **Commit:** `Store the winning Kamp of each battle while extracting`.

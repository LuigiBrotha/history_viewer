# Uboat.net Scraper Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable crawler for uboat.net that stores every commissioned U-boat and the dated routes of its patrols in SQLite, plus a read-only FastAPI query API over that data — ready for a later Leaflet frontend to consume.

**Architecture:** Mirrors the sibling project `HuizenDI` exactly: FastAPI + `wireup` DI container, async SQLAlchemy on `aiosqlite`, `app/core` / `app/http/api` / `app/services` layout, `RequestHandlerRegistry` auto-discovery. Scraping uses sync `requests` + `selectolax` (matching HuizenDI's `DefaultScraper`), driven from a standalone async crawl script (`app/crawl.py`) via `asyncio.to_thread` — not an HTTP-triggered background task, since a full crawl runs many hours at the required 10s-per-request pace.

**Tech Stack:** Python 3.12, FastAPI, `wireup`, SQLAlchemy 2.0 (async) + `aiosqlite`, `requests`, `selectolax`, `pydantic-settings`, `pytest` + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-08-28-uboat-scraper-design.md`

## Global Constraints

- Crawl politeness: sequential requests only, minimum 10 seconds between requests to uboat.net (`CRAWL_DELAY_SECONDS` setting, default `10.0`), distinct User-Agent string. No concurrency anywhere in the crawl path.
- HTTP/parsing: sync `requests` + `selectolax`, never a headless browser — route coordinates come from a regex over an inline `<script>` block, not JS execution.
- The crawl is triggered by running `app/crawl.py` manually (`poetry run python -m app.crawl`), never by an HTTP endpoint.
- Scope: only the main "all U-boats" listing (`/boats/listing.html`, ~1153 boats). Foreign/never-commissioned categories and attack/sinking event markers are out of scope — do not model them.
- All storage is async SQLAlchemy on `sqlite+aiosqlite`, following HuizenDI's `AdRecord`/`AdRepository`/`SiteHealthRepository` conventions (Core `insert(...).on_conflict_do_update(...)` upserts, plain repository classes with a constructor-injected `AsyncSession`, no ORM unit-of-work reliance across repositories).
- Every scraper's HTML-parsing logic must be a pure function taking already-fetched HTML text (or a page URL for relative-link resolution) and returning a dataclass — no I/O inside parse functions, so they're testable against saved fixtures with no mocking.

---

### Task 1: Project scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `.env` (untracked, gitignored)
- Create: `app/__init__.py`, `app/core/__init__.py`, `app/http/__init__.py`, `app/http/api/__init__.py`, `app/http/api/uboats/__init__.py`, `app/services/__init__.py`, `app/services/storage/__init__.py`, `app/services/scraping/__init__.py`, `app/services/scraping/uboat_net/__init__.py`, `app/services/export/__init__.py`
- Create: `app/core/config.py`
- Create: `app/core/container.py`
- Create: `app/services/request_handler_registry.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`, `tests/services/__init__.py`, `tests/services/storage/__init__.py`, `tests/services/scraping/__init__.py`, `tests/services/scraping/uboat_net/__init__.py`, `tests/http/__init__.py`, `tests/http/api/__init__.py`

**Interfaces:**
- Produces: `app.core.config.settings` (a `Settings` instance) — every later task that needs configuration imports this. `app.services.request_handler_registry.RequestHandlerRegistry` — an `@injectable` class whose `__iter__` yields every `RequestHandler` class found under `settings.HTTP_DIR`.

- [ ] **Step 1: Add dependencies to `pyproject.toml`**

Replace the file's dependency sections (keep `[tool.poetry]` metadata as-is):

```toml
[tool.poetry.dependencies]
python = ">=3.12,<3.15"
wireup = "^2.12.0"
fastapi = "^0.139.2"
pydantic-settings = "^2.14.2"
uvicorn = "^0.51.0"
requests = "^2.34.2"
selectolax = "^0.4.11"
sqlalchemy = {extras = ["asyncio"], version = "^2.0.51"}
aiosqlite = "^0.22.1"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.4"
pytest-asyncio = "^1.4.0"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Install dependencies**

Run: `cd /home/scout/PycharmProjects/uboats && poetry install`
Expected: completes without error, creates/updates `poetry.lock`.

- [ ] **Step 3: Create `.env`**

```
BASE_URL=http://localhost:8000
ROOT_PATH=
BASE_DIR=app
HTTP_DIR=app/http
```

- [ ] **Step 4: Create empty `__init__.py` package markers**

Run:
```bash
touch app/__init__.py app/core/__init__.py app/http/__init__.py app/http/api/__init__.py \
      app/http/api/uboats/__init__.py app/services/__init__.py app/services/storage/__init__.py \
      app/services/scraping/__init__.py app/services/scraping/uboat_net/__init__.py app/services/export/__init__.py \
      tests/__init__.py tests/services/__init__.py tests/services/storage/__init__.py \
      tests/services/scraping/__init__.py tests/services/scraping/uboat_net/__init__.py \
      tests/http/__init__.py tests/http/api/__init__.py
```

- [ ] **Step 5: Write `app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[".env", ".env.local"], case_sensitive=True)

    APP_NAME: str = "Uboats"
    APP_VERSION: str = "0.0.1"
    DESCRIPTION: str = "Applicatie voor het scrapen van uboat.net"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./uboats.db"

    BASE_URL: str
    ROOT_PATH: str

    BASE_DIR: str
    HTTP_DIR: str

    CRAWLER_CONTACT: str = ""
    CRAWL_DELAY_SECONDS: float = 10.0


settings = Settings()
```

- [ ] **Step 6: Write `app/core/container.py`**

```python
import wireup
import app.core
import app.services
import app.http
import wireup.integration.fastapi

from app.core.config import settings

container = wireup.create_async_container(
    injectables=[wireup.integration.fastapi.request_factory, app.core, app.services, app.http],
    config=settings,
)
```

- [ ] **Step 7: Write `app/services/request_handler_registry.py`**

```python
import importlib
from pathlib import Path

from wireup import injectable

from app.core.config import settings


@injectable
class RequestHandlerRegistry:
    def __init__(self) -> None:
        self._scan_dir = Path(settings.HTTP_DIR)

    def __iter__(self):
        for path in sorted(self._scan_dir.rglob('*.py')):
            if path.name == '__init__.py':
                continue
            module_name = ".".join(path.with_suffix("").parts)
            module = importlib.import_module(module_name)
            handler = getattr(module, "RequestHandler", None)
            if handler:
                yield handler
```

- [ ] **Step 8: Write `app/main.py`**

```python
import uvicorn
import wireup.integration.fastapi
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import settings
from app.core.container import container
from fastapi import FastAPI

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    debug=settings.DEBUG,
)

with async_container_force_sync_scope(container) as scope:
    request_handler_registry = scope.get(RequestHandlerRegistry)
    handlers = list(request_handler_registry)

wireup.integration.fastapi.setup(container, app, class_based_handlers=handlers)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 9: Verify the app boots**

Run: `poetry run python -c "import app.main; print('ok')"`
Expected: prints `ok` with no traceback. (There are no routes yet — that's expected; this only proves settings/container/registry wiring works.)

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml poetry.lock app tests
git commit -m "Scaffold uboats FastAPI + wireup project structure"
```

---

### Task 2: Storage models and database bootstrap

**Files:**
- Create: `app/services/storage/models.py`
- Create: `app/services/storage/database.py`
- Test: `tests/services/storage/test_database.py`

**Interfaces:**
- Produces: `Boat`, `Patrol`, `RoutePoint`, `BoatCrawlState` ORM models (`app.services.storage.models`). `create_engine(database_url: str) -> AsyncEngine`, `create_session_factory(engine) -> async_sessionmaker[AsyncSession]`, `async def init_models(engine) -> None` (`app.services.storage.database`) — every later storage/crawl task uses these three functions to build a session factory in tests and in `app/crawl.py`.

- [ ] **Step 1: Write the failing test**

`tests/services/storage/test_database.py`:

```python
from datetime import date

from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Boat, BoatCrawlState, Patrol, RoutePoint


async def test_init_models_creates_tables_and_boat_round_trips(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        session.add(Boat(
            slug="u99",
            number="U-99",
            type="VIIB",
            builder="F. Krupp Germaniawerft AG, Kiel",
            laid_down=date(1939, 3, 31),
            launched=date(1940, 3, 12),
            commissioned=date(1940, 4, 18),
            fate="Scuttled",
        ))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(Boat.__table__.select())
        row = result.first()

    assert row.slug == "u99"
    assert row.laid_down == date(1939, 3, 31)

    await engine.dispose()


async def test_patrol_and_route_point_round_trip_via_foreign_key(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        boat = Boat(slug="u99", number="U-99")
        session.add(boat)
        await session.flush()
        patrol = Patrol(boat_id=boat.id, external_id="patrol_4754", patrol_number=1)
        session.add(patrol)
        await session.flush()
        session.add(RoutePoint(patrol_id=patrol.id, sequence=0, lat=54.3667, lng=10.1667, date=date(1940, 6, 18)))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(RoutePoint.__table__.select())
        row = result.first()

    assert row.lat == 54.3667
    assert row.date == date(1940, 6, 18)

    await engine.dispose()


async def test_boat_crawl_state_round_trip(tmp_path):
    from datetime import datetime, timezone

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        session.add(BoatCrawlState(slug="u99", status="success", last_attempt_at=now, last_success_at=now))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(BoatCrawlState.__table__.select())
        row = result.first()

    assert row.status == "success"
    assert row.last_attempt_at.tzinfo is not None

    await engine.dispose()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/services/storage/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.storage.models'` (or `database`).

- [ ] **Step 3: Write `app/services/storage/models.py`**

```python
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores naive UTC datetimes but always returns timezone-aware UTC datetimes.

    SQLite (via aiosqlite) silently discards tzinfo on write and returns naive
    datetimes on read, regardless of whether the column is declared with
    DateTime(timezone=True). This TypeDecorator makes that limitation
    transparent to consumers of the ORM.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Boat(Base):
    __tablename__ = "boats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    builder: Mapped[str | None] = mapped_column(String, nullable=True)
    laid_down: Mapped[date | None] = mapped_column(Date, nullable=True)
    launched: Mapped[date | None] = mapped_column(Date, nullable=True)
    commissioned: Mapped[date | None] = mapped_column(Date, nullable=True)
    fate: Mapped[str | None] = mapped_column(String, nullable=True)

    patrols: Mapped[list["Patrol"]] = relationship(back_populates="boat", cascade="all, delete-orphan")


class Patrol(Base):
    __tablename__ = "patrols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boat_id: Mapped[int] = mapped_column(ForeignKey("boats.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    patrol_number: Mapped[int] = mapped_column(Integer, nullable=False)
    commander: Mapped[str | None] = mapped_column(String, nullable=True)
    departure_port: Mapped[str | None] = mapped_column(String, nullable=True)
    departure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    arrival_port: Mapped[str | None] = mapped_column(String, nullable=True)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_at_sea: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tonnage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    boat: Mapped["Boat"] = relationship(back_populates="patrols")
    route_points: Mapped[list["RoutePoint"]] = relationship(back_populates="patrol", cascade="all, delete-orphan")


class RoutePoint(Base):
    __tablename__ = "route_points"
    __table_args__ = (UniqueConstraint("patrol_id", "sequence", name="uq_route_points_patrol_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patrol_id: Mapped[int] = mapped_column(ForeignKey("patrols.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)

    patrol: Mapped["Patrol"] = relationship(back_populates="route_points")


class BoatCrawlState(Base):
    __tablename__ = "boat_crawl_state"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Write `app/services/storage/database.py`**

```python
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.services.storage.models import Base


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/storage/test_database.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/storage/models.py app/services/storage/database.py tests/services/storage/test_database.py
git commit -m "Add Boat/Patrol/RoutePoint/BoatCrawlState storage models"
```

---

### Task 3: Shared scraping utilities and types

**Files:**
- Create: `app/services/scraping/uboat_net/text.py`
- Create: `app/services/scraping/uboat_net/dates.py`
- Create: `app/services/scraping/uboat_net/types.py`
- Test: `tests/services/scraping/uboat_net/test_dates.py`
- Test: `tests/services/scraping/uboat_net/test_text.py`

**Interfaces:**
- Produces: `clean_text(node) -> str` (`app.services.scraping.uboat_net.text`) — used by every HTML parser task. `parse_date(text: str | None) -> date | None` and `parse_iso_date(text: str | None) -> date | None` (`app.services.scraping.uboat_net.dates`). Dataclasses `BoatRef`, `BoatData`, `RoutePointData`, `PatrolSummary`, `PatrolDetail` (`app.services.scraping.uboat_net.types`) — the shape every scraper module and repository upsert method in later tasks consumes.

- [ ] **Step 1: Write the failing tests**

`tests/services/scraping/uboat_net/test_dates.py`:

```python
from datetime import date

from app.services.scraping.uboat_net.dates import parse_date, parse_iso_date


def test_parse_date_valid():
    assert parse_date("18 Jun 1940") == date(1940, 6, 18)


def test_parse_date_strips_trailing_nbsp():
    assert parse_date("18 Jun 1940\xa0\xa0") == date(1940, 6, 18)


def test_parse_date_none_input_returns_none():
    assert parse_date(None) is None


def test_parse_date_empty_string_returns_none():
    assert parse_date("") is None


def test_parse_date_unknown_text_returns_none():
    assert parse_date("Unknown") is None


def test_parse_iso_date_valid():
    assert parse_iso_date("1940-06-18") == date(1940, 6, 18)


def test_parse_iso_date_none_returns_none():
    assert parse_iso_date(None) is None


def test_parse_iso_date_malformed_returns_none():
    assert parse_iso_date("not-a-date") is None
```

`tests/services/scraping/uboat_net/test_text.py`:

```python
from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.text import clean_text


def test_clean_text_collapses_whitespace_between_inline_elements():
    node = HTMLParser("<td>Kptlt.  <a>Otto Kretschmer</a></td>").css_first("td")

    assert clean_text(node) == "Kptlt. Otto Kretschmer"


def test_clean_text_strips_leading_and_trailing_whitespace():
    node = HTMLParser("<p>  hello world  </p>").css_first("p")

    assert clean_text(node) == "hello world"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_dates.py tests/services/scraping/uboat_net/test_text.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/services/scraping/uboat_net/dates.py`**

```python
from datetime import date

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").strip()
    parts = cleaned.split()
    if len(parts) != 3:
        return None
    day_text, month_text, year_text = parts
    month = _MONTHS.get(month_text[:3].title())
    if month is None:
        return None
    try:
        return date(int(year_text), month, int(day_text))
    except ValueError:
        return None


def parse_iso_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
```

- [ ] **Step 4: Write `app/services/scraping/uboat_net/text.py`**

```python
def clean_text(node) -> str:
    return " ".join(node.text(deep=True, separator=" ", strip=True).split())
```

- [ ] **Step 5: Write `app/services/scraping/uboat_net/types.py`**

```python
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class BoatRef:
    slug: str
    number: str


@dataclass(frozen=True)
class BoatData:
    slug: str
    number: str
    type: str | None
    builder: str | None
    laid_down: date | None
    launched: date | None
    commissioned: date | None
    fate: str | None


@dataclass(frozen=True)
class RoutePointData:
    sequence: int
    lat: float
    lng: float
    date: date | None


@dataclass(frozen=True)
class PatrolSummary:
    external_id: str
    patrol_number: int
    commander: str | None
    departure_port: str | None
    departure_date: date | None
    arrival_port: str | None
    arrival_date: date | None
    days_at_sea: int | None
    tonnage: int | None
    detail_url: str


@dataclass(frozen=True)
class PatrolDetail:
    description: str | None
    route_points: list[RoutePointData] = field(default_factory=list)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_dates.py tests/services/scraping/uboat_net/test_text.py -v`
Expected: 10 passed.

- [ ] **Step 7: Commit**

```bash
git add app/services/scraping/uboat_net/text.py app/services/scraping/uboat_net/dates.py \
        app/services/scraping/uboat_net/types.py tests/services/scraping/uboat_net/test_dates.py \
        tests/services/scraping/uboat_net/test_text.py
git commit -m "Add shared uboat.net scraping utilities and dataclasses"
```

---

### Task 4: API output dataclasses

**Files:**
- Create: `app/services/export/uboats.py`

**Interfaces:**
- Consumes: nothing (pure dataclasses).
- Produces: `BoatSummary`, `PatrolSummaryOut`, `BoatDetail`, `RoutePointOut`, `PatrolRouteOut` — Task 5/6 repository read methods return these; Task 14 endpoints return them directly as FastAPI response bodies.

- [ ] **Step 1: Write `app/services/export/uboats.py`**

No test file — these are plain dataclasses with no logic, matching how HuizenDI's `app/services/export/ad.py` (`Ad`) has no dedicated test either; they're exercised by every repository test in Tasks 5–6.

```python
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class BoatSummary:
    slug: str
    number: str
    type: str | None
    fate: str | None
    patrol_count: int


@dataclass(frozen=True)
class PatrolSummaryOut:
    external_id: str
    patrol_number: int
    commander: str | None
    departure_port: str | None
    departure_date: date | None
    arrival_port: str | None
    arrival_date: date | None
    days_at_sea: int | None
    tonnage: int | None


@dataclass(frozen=True)
class BoatDetail:
    slug: str
    number: str
    type: str | None
    builder: str | None
    laid_down: date | None
    launched: date | None
    commissioned: date | None
    fate: str | None
    patrols: list[PatrolSummaryOut] = field(default_factory=list)


@dataclass(frozen=True)
class RoutePointOut:
    sequence: int
    lat: float
    lng: float
    date: date | None


@dataclass(frozen=True)
class PatrolRouteOut:
    boat_slug: str
    boat_number: str
    external_id: str
    departure_date: date | None
    arrival_date: date | None
    points: list[RoutePointOut] = field(default_factory=list)
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `poetry run python -c "from app.services.export.uboats import BoatSummary, PatrolSummaryOut, BoatDetail, RoutePointOut, PatrolRouteOut; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/services/export/uboats.py
git commit -m "Add API output dataclasses for boats and patrol routes"
```

---

### Task 5: BoatRepository

**Files:**
- Create: `app/services/storage/boat_repository.py`
- Test: `tests/services/storage/test_boat_repository.py`

**Interfaces:**
- Consumes: `Boat` (Task 2), `BoatData` (Task 3), `BoatSummary`/`BoatDetail`/`PatrolSummaryOut` (Task 4).
- Produces: `class BoatRepository(session: AsyncSession)` with `async def upsert_boat(data: BoatData) -> None`, `async def get_id_by_slug(slug: str) -> int | None`, `async def list_summaries() -> list[BoatSummary]`, `async def get_detail(slug: str) -> BoatDetail | None`. Task 13 (`app/crawl.py`) uses `upsert_boat`/`get_id_by_slug`; Task 14 (query API) uses `list_summaries`/`get_detail`.

- [ ] **Step 1: Write the failing test**

`tests/services/storage/test_boat_repository.py`:

```python
from datetime import date

from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return create_session_factory(engine)


def _boat_data(slug="u99", **overrides):
    defaults = dict(
        slug=slug,
        number="U-99",
        type="VIIB",
        builder="F. Krupp Germaniawerft AG, Kiel",
        laid_down=date(1939, 3, 31),
        launched=date(1940, 3, 12),
        commissioned=date(1940, 4, 18),
        fate="Scuttled",
    )
    defaults.update(overrides)
    return BoatData(**defaults)


async def test_upsert_boat_inserts_new_boat(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(_boat_data())
        summaries = await BoatRepository(session).list_summaries()

    assert len(summaries) == 1
    assert summaries[0].slug == "u99"
    assert summaries[0].number == "U-99"
    assert summaries[0].patrol_count == 0


async def test_upsert_boat_updates_existing_row_on_conflict(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        repo = BoatRepository(session)
        await repo.upsert_boat(_boat_data(fate="Scuttled"))
        await repo.upsert_boat(_boat_data(fate="Sunk by depth charges"))
        summaries = await repo.list_summaries()

    assert len(summaries) == 1
    assert summaries[0].fate == "Sunk by depth charges"


async def test_get_id_by_slug_returns_none_for_unknown_slug(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        boat_id = await BoatRepository(session).get_id_by_slug("unknown")

    assert boat_id is None


async def test_get_id_by_slug_returns_id_after_upsert(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        repo = BoatRepository(session)
        await repo.upsert_boat(_boat_data())
        boat_id = await repo.get_id_by_slug("u99")

    assert isinstance(boat_id, int)


async def test_get_detail_returns_none_for_unknown_slug(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        detail = await BoatRepository(session).get_detail("unknown")

    assert detail is None


async def test_get_detail_returns_boat_fields_and_empty_patrols(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(_boat_data())
        detail = await BoatRepository(session).get_detail("u99")

    assert detail.slug == "u99"
    assert detail.type == "VIIB"
    assert detail.laid_down == date(1939, 3, 31)
    assert detail.patrols == []


async def test_list_summaries_orders_by_slug(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        repo = BoatRepository(session)
        await repo.upsert_boat(_boat_data(slug="u255", number="U-255"))
        await repo.upsert_boat(_boat_data(slug="u99", number="U-99"))
        summaries = await repo.list_summaries()

    assert [s.slug for s in summaries] == ["u255", "u99"]
```

Note: the last test asserts SQLite's default text ordering (`"u255" < "u99"` lexicographically) — this documents actual behavior rather than assuming numeric boat-number ordering, which isn't implemented.

- [ ] **Step 2: Run the test to verify it fails**

Run: `poetry run pytest tests/services/storage/test_boat_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.storage.boat_repository'`.

- [ ] **Step 3: Write `app/services/storage/boat_repository.py`**

```python
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import BoatDetail, BoatSummary, PatrolSummaryOut
from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.models import Boat, Patrol


class BoatRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_boat(self, data: BoatData) -> None:
        stmt = insert(Boat).values(
            slug=data.slug,
            number=data.number,
            type=data.type,
            builder=data.builder,
            laid_down=data.laid_down,
            launched=data.launched,
            commissioned=data.commissioned,
            fate=data.fate,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={
                "number": stmt.excluded.number,
                "type": stmt.excluded.type,
                "builder": stmt.excluded.builder,
                "laid_down": stmt.excluded.laid_down,
                "launched": stmt.excluded.launched,
                "commissioned": stmt.excluded.commissioned,
                "fate": stmt.excluded.fate,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_id_by_slug(self, slug: str) -> int | None:
        result = await self._session.execute(select(Boat.id).where(Boat.slug == slug))
        return result.scalar_one_or_none()

    async def list_summaries(self) -> list[BoatSummary]:
        patrol_count = func.count(Patrol.id).label("patrol_count")
        stmt = (
            select(Boat.slug, Boat.number, Boat.type, Boat.fate, patrol_count)
            .outerjoin(Patrol, Patrol.boat_id == Boat.id)
            .group_by(Boat.id)
            .order_by(Boat.slug)
        )
        result = await self._session.execute(stmt)
        return [
            BoatSummary(slug=row.slug, number=row.number, type=row.type, fate=row.fate, patrol_count=row.patrol_count)
            for row in result.all()
        ]

    async def get_detail(self, slug: str) -> BoatDetail | None:
        boat_result = await self._session.execute(select(Boat).where(Boat.slug == slug))
        boat = boat_result.scalar_one_or_none()
        if boat is None:
            return None

        patrols_result = await self._session.execute(
            select(Patrol).where(Patrol.boat_id == boat.id).order_by(Patrol.patrol_number)
        )
        patrols = [
            PatrolSummaryOut(
                external_id=p.external_id,
                patrol_number=p.patrol_number,
                commander=p.commander,
                departure_port=p.departure_port,
                departure_date=p.departure_date,
                arrival_port=p.arrival_port,
                arrival_date=p.arrival_date,
                days_at_sea=p.days_at_sea,
                tonnage=p.tonnage,
            )
            for p in patrols_result.scalars().all()
        ]

        return BoatDetail(
            slug=boat.slug,
            number=boat.number,
            type=boat.type,
            builder=boat.builder,
            laid_down=boat.laid_down,
            launched=boat.launched,
            commissioned=boat.commissioned,
            fate=boat.fate,
            patrols=patrols,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/storage/test_boat_repository.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/storage/boat_repository.py tests/services/storage/test_boat_repository.py
git commit -m "Add BoatRepository with upsert and read methods"
```

---

### Task 6: PatrolRepository

**Files:**
- Create: `app/services/storage/patrol_repository.py`
- Test: `tests/services/storage/test_patrol_repository.py`

**Interfaces:**
- Consumes: `Patrol`, `RoutePoint`, `Boat` (Task 2), `PatrolSummary`, `PatrolDetail`, `RoutePointData` (Task 3), `PatrolRouteOut`, `RoutePointOut` (Task 4), `BoatRepository` (Task 5, used only in the test to seed a boat).
- Produces: `class PatrolRepository(session: AsyncSession)` with `async def upsert_patrol(boat_id: int, summary: PatrolSummary, detail: PatrolDetail) -> None` and `async def list_routes() -> list[PatrolRouteOut]`. Task 13 (`app/crawl.py`) uses `upsert_patrol`; Task 14 (query API) uses `list_routes`.

- [ ] **Step 1: Write the failing test**

`tests/services/storage/test_patrol_repository.py`:

```python
from datetime import date

from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.patrol_repository import PatrolRepository


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return create_session_factory(engine)


async def _seed_boat(session, slug="u99", number="U-99"):
    repo = BoatRepository(session)
    await repo.upsert_boat(BoatData(
        slug=slug, number=number, type=None, builder=None,
        laid_down=None, launched=None, commissioned=None, fate=None,
    ))
    return await repo.get_id_by_slug(slug)


def _summary(external_id="patrol_4754", **overrides):
    defaults = dict(
        external_id=external_id,
        patrol_number=1,
        commander="Kptlt. Otto Kretschmer",
        departure_port="Kiel",
        departure_date=date(1940, 6, 18),
        arrival_port="Wilhelmshaven",
        arrival_date=date(1940, 6, 25),
        days_at_sea=8,
        tonnage=None,
        detail_url="https://uboat.net/boats/patrols/patrol_4754.html",
    )
    defaults.update(overrides)
    return PatrolSummary(**defaults)


def _detail(points=None, description="Left Germany for a patrol."):
    return PatrolDetail(description=description, route_points=points or [])


async def test_upsert_patrol_inserts_patrol_and_route_points(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        points = [
            RoutePointData(sequence=0, lat=54.3667, lng=10.1667, date=date(1940, 6, 18)),
            RoutePointData(sequence=1, lat=54.15, lng=7.25, date=date(1940, 6, 19)),
        ]
        await PatrolRepository(session).upsert_patrol(boat_id, _summary(), _detail(points))
        routes = await PatrolRepository(session).list_routes()

    assert len(routes) == 1
    assert routes[0].boat_slug == "u99"
    assert routes[0].external_id == "patrol_4754"
    assert len(routes[0].points) == 2
    assert routes[0].points[0].lat == 54.3667
    assert routes[0].points[0].date == date(1940, 6, 18)


async def test_upsert_patrol_replaces_route_points_on_conflict(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail([
            RoutePointData(sequence=0, lat=1.0, lng=1.0, date=None),
            RoutePointData(sequence=1, lat=2.0, lng=2.0, date=None),
        ]))
        await repo.upsert_patrol(boat_id, _summary(), _detail([
            RoutePointData(sequence=0, lat=9.0, lng=9.0, date=None),
        ]))
        routes = await repo.list_routes()

    assert len(routes[0].points) == 1
    assert routes[0].points[0].lat == 9.0


async def test_upsert_patrol_updates_summary_fields_on_conflict(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(tonnage=None), _detail())
        await repo.upsert_patrol(boat_id, _summary(tonnage=22719), _detail())
        detail = await BoatRepository(session).get_detail("u99")

    assert detail.patrols[0].tonnage == 22719


async def test_list_routes_orders_by_boat_slug_then_patrol_number(tmp_path):
    session_factory = await _session_factory(tmp_path)

    async with session_factory() as session:
        boat_a = await _seed_boat(session, slug="u100", number="U-100")
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_a, _summary(external_id="patrol_2", patrol_number=2), _detail())
        await repo.upsert_patrol(boat_a, _summary(external_id="patrol_1", patrol_number=1), _detail())
        routes = await repo.list_routes()

    assert [r.external_id for r in routes] == ["patrol_1", "patrol_2"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `poetry run pytest tests/services/storage/test_patrol_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.storage.patrol_repository'`.

- [ ] **Step 3: Write `app/services/storage/patrol_repository.py`**

```python
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import PatrolRouteOut, RoutePointOut
from app.services.scraping.uboat_net.types import PatrolDetail, PatrolSummary
from app.services.storage.models import Boat, Patrol, RoutePoint


class PatrolRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_patrol(self, boat_id: int, summary: PatrolSummary, detail: PatrolDetail) -> None:
        stmt = insert(Patrol).values(
            boat_id=boat_id,
            external_id=summary.external_id,
            patrol_number=summary.patrol_number,
            commander=summary.commander,
            departure_port=summary.departure_port,
            departure_date=summary.departure_date,
            arrival_port=summary.arrival_port,
            arrival_date=summary.arrival_date,
            days_at_sea=summary.days_at_sea,
            tonnage=summary.tonnage,
            description=detail.description,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "boat_id": stmt.excluded.boat_id,
                "patrol_number": stmt.excluded.patrol_number,
                "commander": stmt.excluded.commander,
                "departure_port": stmt.excluded.departure_port,
                "departure_date": stmt.excluded.departure_date,
                "arrival_port": stmt.excluded.arrival_port,
                "arrival_date": stmt.excluded.arrival_date,
                "days_at_sea": stmt.excluded.days_at_sea,
                "tonnage": stmt.excluded.tonnage,
                "description": stmt.excluded.description,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

        patrol_id = await self._session.scalar(
            select(Patrol.id).where(Patrol.external_id == summary.external_id)
        )

        await self._session.execute(delete(RoutePoint).where(RoutePoint.patrol_id == patrol_id))
        for point in detail.route_points:
            self._session.add(RoutePoint(
                patrol_id=patrol_id,
                sequence=point.sequence,
                lat=point.lat,
                lng=point.lng,
                date=point.date,
            ))
        await self._session.commit()

    async def list_routes(self) -> list[PatrolRouteOut]:
        stmt = (
            select(Patrol, Boat.slug, Boat.number)
            .join(Boat, Patrol.boat_id == Boat.id)
            .order_by(Boat.slug, Patrol.patrol_number)
        )
        result = await self._session.execute(stmt)
        routes = []
        for patrol, boat_slug, boat_number in result.all():
            points_result = await self._session.execute(
                select(RoutePoint).where(RoutePoint.patrol_id == patrol.id).order_by(RoutePoint.sequence)
            )
            points = [
                RoutePointOut(sequence=pt.sequence, lat=pt.lat, lng=pt.lng, date=pt.date)
                for pt in points_result.scalars().all()
            ]
            routes.append(PatrolRouteOut(
                boat_slug=boat_slug,
                boat_number=boat_number,
                external_id=patrol.external_id,
                departure_date=patrol.departure_date,
                arrival_date=patrol.arrival_date,
                points=points,
            ))
        return routes
```

Note: `list_routes` issues one extra query per patrol to fetch its points. Acceptable at the current scale (tens of patrols); revisit with a single joined query if the full ~1150-boat crawl makes this endpoint slow.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/storage/test_patrol_repository.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/storage/patrol_repository.py tests/services/storage/test_patrol_repository.py
git commit -m "Add PatrolRepository with upsert and route-list read method"
```

---

### Task 7: BoatCrawlStateRepository

**Files:**
- Create: `app/services/storage/boat_crawl_state_repository.py`
- Test: `tests/services/storage/test_boat_crawl_state_repository.py`

**Interfaces:**
- Consumes: `BoatCrawlState` (Task 2).
- Produces: `class BoatCrawlStateRepository(session: AsyncSession)` with `async def record_success(slug: str) -> None`, `async def record_failure(slug: str, error: str) -> None`, `async def get(slug: str) -> BoatCrawlState | None`. Task 13 (`app/crawl.py`) uses all three.

- [ ] **Step 1: Write the failing test**

`tests/services/storage/test_boat_crawl_state_repository.py` (directly mirrors HuizenDI's `test_site_health_repository.py`):

```python
from contextlib import asynccontextmanager

from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


@asynccontextmanager
async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def test_record_success_sets_status_and_timestamps(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = BoatCrawlStateRepository(session)
            await repo.record_success("u99")
            state = await repo.get("u99")

    assert state.status == "success"
    assert state.last_success_at is not None
    assert state.last_attempt_at is not None
    assert state.last_error is None


async def test_record_failure_sets_status_and_error(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = BoatCrawlStateRepository(session)
            await repo.record_failure("u99", "connection timed out")
            state = await repo.get("u99")

    assert state.status == "failed"
    assert state.last_error == "connection timed out"
    assert state.last_success_at is None


async def test_get_returns_none_for_unknown_slug(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            state = await BoatCrawlStateRepository(session).get("unknown")

    assert state is None


async def test_success_after_failure_clears_error_and_sets_success(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = BoatCrawlStateRepository(session)
            await repo.record_failure("u99", "boom")
            await repo.record_success("u99")
            session.expire_all()
            state = await repo.get("u99")

    assert state.status == "success"
    assert state.last_error is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `poetry run pytest tests/services/storage/test_boat_crawl_state_repository.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/services/storage/boat_crawl_state_repository.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.storage.models import BoatCrawlState


class BoatCrawlStateRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def record_success(self, slug: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(BoatCrawlState).values(
            slug=slug, status="success", last_attempt_at=now, last_success_at=now, last_error=None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={"status": "success", "last_attempt_at": now, "last_success_at": now, "last_error": None},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def record_failure(self, slug: str, error: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(BoatCrawlState).values(
            slug=slug, status="failed", last_attempt_at=now, last_success_at=None, last_error=error,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={"status": "failed", "last_attempt_at": now, "last_error": error},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get(self, slug: str) -> BoatCrawlState | None:
        result = await self._session.execute(select(BoatCrawlState).where(BoatCrawlState.slug == slug))
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/storage/test_boat_crawl_state_repository.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/storage/boat_crawl_state_repository.py tests/services/storage/test_boat_crawl_state_repository.py
git commit -m "Add BoatCrawlStateRepository for resumable-crawl bookkeeping"
```

---

### Task 8: PoliteHttpClient

**Files:**
- Create: `app/services/scraping/uboat_net/http_client.py`
- Test: `tests/services/scraping/uboat_net/test_http_client.py`

**Interfaces:**
- Produces: `BASE_URL = "https://uboat.net"`, `build_user_agent(contact: str | None) -> str`, `class PoliteHttpClient(delay_seconds: float, user_agent: str)` with `def get_text(url: str) -> str`. Tasks 9–12's `fetch_*` wrappers and Task 13's `app/crawl.py` use `PoliteHttpClient` and `BASE_URL`.

- [ ] **Step 1: Write the failing test**

`tests/services/scraping/uboat_net/test_http_client.py`:

```python
from unittest.mock import Mock, patch

from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent


def test_build_user_agent_without_contact():
    assert build_user_agent("") == "uboats-scraper/0.1"


def test_build_user_agent_with_contact():
    assert build_user_agent("d_verhoef@hotmail.com") == "uboats-scraper/0.1 (+contact: d_verhoef@hotmail.com)"


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_first_request_does_not_sleep(mock_get, mock_monotonic, mock_sleep):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    mock_monotonic.return_value = 100.0
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    result = client.get_text("https://uboat.net/x")

    assert result == "hello"
    mock_sleep.assert_not_called()


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_second_request_sleeps_for_remaining_delay(mock_get, mock_monotonic, mock_sleep):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    mock_monotonic.side_effect = [100.0, 103.0, 103.0]
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    client.get_text("https://uboat.net/x")
    client.get_text("https://uboat.net/y")

    mock_sleep.assert_called_once_with(7.0)


@patch("app.services.scraping.uboat_net.http_client.time.sleep")
@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_does_not_sleep_when_elapsed_already_exceeds_delay(mock_get, mock_monotonic, mock_sleep):
    mock_get.return_value = Mock(text="hello", raise_for_status=Mock())
    mock_monotonic.side_effect = [100.0, 115.0, 115.0]
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    client.get_text("https://uboat.net/x")
    client.get_text("https://uboat.net/y")

    mock_sleep.assert_not_called()


@patch("app.services.scraping.uboat_net.http_client.time.monotonic")
@patch("app.services.scraping.uboat_net.http_client.requests.Session.get")
def test_get_text_raises_on_http_error(mock_get, mock_monotonic):
    mock_monotonic.return_value = 100.0
    response = Mock(text="", raise_for_status=Mock(side_effect=RuntimeError("404")))
    mock_get.return_value = response
    client = PoliteHttpClient(delay_seconds=10, user_agent="test-agent")

    try:
        client.get_text("https://uboat.net/missing")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_http_client.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/services/scraping/uboat_net/http_client.py`**

```python
import time

import requests

BASE_URL = "https://uboat.net"

_DEFAULT_USER_AGENT = "uboats-scraper/0.1"


def build_user_agent(contact: str | None) -> str:
    if contact:
        return f"{_DEFAULT_USER_AGENT} (+contact: {contact})"
    return _DEFAULT_USER_AGENT


class PoliteHttpClient:
    def __init__(self, delay_seconds: float, user_agent: str):
        self._delay_seconds = delay_seconds
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._last_request_at: float | None = None

    def get_text(self, url: str) -> str:
        self._wait_for_slot()
        response = self._session.get(url)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response.text

    def _wait_for_slot(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_http_client.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/scraping/uboat_net/http_client.py tests/services/scraping/uboat_net/test_http_client.py
git commit -m "Add rate-limited PoliteHttpClient for uboat.net requests"
```

---

### Task 9: Listing scraper

**Files:**
- Create: `app/services/scraping/uboat_net/listing.py`
- Create: `tests/fixtures/uboat_net/listing.html` (copied from a real fetch)
- Test: `tests/services/scraping/uboat_net/test_listing.py`

**Interfaces:**
- Consumes: `BoatRef` (Task 3), `PoliteHttpClient`, `BASE_URL` (Task 8).
- Produces: `parse_listing(html: str) -> list[BoatRef]`, `fetch_listing(client: PoliteHttpClient) -> list[BoatRef]`. Task 13 (`app/crawl.py`) calls `fetch_listing` to get the full list of boats to crawl.

- [ ] **Step 1: Copy the fixture**

The listing page was already fetched and verified during design (single page, ~1153 boat links, no pagination). Copy it into the test fixtures directory:

```bash
mkdir -p tests/fixtures/uboat_net
cp /tmp/claude-1000/-home-scout-PycharmProjects-uboats/f70db281-1dd9-4e25-903a-d304ad9df26b/scratchpad/listing.html \
   tests/fixtures/uboat_net/listing.html
```

If that scratchpad path is no longer available, refetch it: `curl -s -A "uboats-scraper/0.1" "https://uboat.net/boats/listing.html" -o tests/fixtures/uboat_net/listing.html` (a single one-off fetch for a fixture; not part of the crawler's own request budget).

- [ ] **Step 2: Write the failing test**

`tests/services/scraping/uboat_net/test_listing.py`:

```python
from pathlib import Path

from app.services.scraping.uboat_net.listing import parse_listing

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "listing.html"


def test_parse_listing_extracts_boat_refs_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    refs = parse_listing(html)

    assert len(refs) > 1000
    slugs = {ref.slug for ref in refs}
    assert "u99" in slugs
    assert "u1000" in slugs


def test_parse_listing_pairs_slug_with_display_number():
    html = _FIXTURE.read_text(encoding="utf-8")

    refs = parse_listing(html)

    by_slug = {ref.slug: ref.number for ref in refs}
    assert by_slug["u1000"] == "U-1000"


def test_parse_listing_deduplicates_repeated_links():
    html = '<a href="/boats/u99.htm">U-99</a> ... <a href="/boats/u99.htm">U-99</a>'

    refs = parse_listing(html)

    assert len(refs) == 1


def test_parse_listing_ignores_non_boat_links():
    html = '<a href="/boats/patrols/u99.html">patrols</a><a href="/boats/u99.htm">U-99</a>'

    refs = parse_listing(html)

    assert len(refs) == 1
    assert refs[0].slug == "u99"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_listing.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `app/services/scraping/uboat_net/listing.py`**

```python
import re

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.types import BoatRef

_SLUG_RE = re.compile(r"^/boats/(u\d+)\.htm$")


def parse_listing(html: str) -> list[BoatRef]:
    parser = HTMLParser(html)
    seen: dict[str, BoatRef] = {}
    for anchor in parser.css("a[href]"):
        href = anchor.attributes.get("href") or ""
        match = _SLUG_RE.match(href)
        if not match:
            continue
        slug = match.group(1)
        if slug in seen:
            continue
        seen[slug] = BoatRef(slug=slug, number=anchor.text(strip=True))
    return list(seen.values())


def fetch_listing(client: PoliteHttpClient) -> list[BoatRef]:
    html = client.get_text(f"{BASE_URL}/boats/listing.html")
    return parse_listing(html)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_listing.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/scraping/uboat_net/listing.py tests/fixtures/uboat_net/listing.html \
        tests/services/scraping/uboat_net/test_listing.py
git commit -m "Add uboat.net boat-listing scraper"
```

---

### Task 10: Boat detail scraper

**Files:**
- Create: `app/services/scraping/uboat_net/boat.py`
- Create: `tests/fixtures/uboat_net/u99.htm` (copied from a real fetch)
- Test: `tests/services/scraping/uboat_net/test_boat.py`

**Interfaces:**
- Consumes: `BoatData` (Task 3), `clean_text` (Task 3), `parse_date` (Task 3), `PoliteHttpClient`, `BASE_URL` (Task 8).
- Produces: `parse_boat(html: str, slug: str) -> BoatData`, `fetch_boat(client: PoliteHttpClient, slug: str) -> BoatData`. Task 13 (`app/crawl.py`) calls `fetch_boat` per boat.

- [ ] **Step 1: Copy the fixture**

```bash
cp /tmp/claude-1000/-home-scout-PycharmProjects-uboats/f70db281-1dd9-4e25-903a-d304ad9df26b/scratchpad/u99.htm \
   tests/fixtures/uboat_net/u99.htm
```

If unavailable, refetch once: `curl -s -A "uboats-scraper/0.1" "https://uboat.net/boats/u99.htm" -o tests/fixtures/uboat_net/u99.htm`.

- [ ] **Step 2: Write the failing test**

`tests/services/scraping/uboat_net/test_boat.py`:

```python
from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.boat import parse_boat

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "u99.htm"


def test_parse_boat_extracts_all_fields_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    boat = parse_boat(html, "u99")

    assert boat.slug == "u99"
    assert boat.number == "U-99"
    assert boat.type == "VIIB"
    assert boat.builder == "F. Krupp Germaniawerft AG, Kiel"
    assert boat.laid_down == date(1939, 3, 31)
    assert boat.launched == date(1940, 3, 12)
    assert boat.commissioned == date(1940, 4, 18)
    assert boat.fate is not None
    assert "Scuttled" in boat.fate


def test_parse_boat_falls_back_to_slug_when_no_h1_present():
    boat = parse_boat("<html><body>no name here</body></html>", "u1")

    assert boat.number == "u1"
    assert boat.type is None
    assert boat.fate is None


def test_parse_boat_missing_profile_table_returns_none_fields():
    boat = parse_boat("<h1>uboat.net</h1><h1>U-1</h1>", "u1")

    assert boat.number == "U-1"
    assert boat.type is None
    assert boat.laid_down is None
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_boat.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `app/services/scraping/uboat_net/boat.py`**

```python
from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_date
from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import BoatData


def _profile_rows(parser: HTMLParser) -> dict[str, list]:
    table = parser.css_first("table.table_subtle")
    rows: dict[str, list] = {}
    if table is None:
        return rows
    for row in table.css("tr"):
        cells = row.css("td")
        if not cells:
            continue
        label = cells[0].text(strip=True)
        rows.setdefault(label, cells)
    return rows


def parse_boat(html: str, slug: str) -> BoatData:
    parser = HTMLParser(html)

    h1_nodes = parser.css("h1")
    number = h1_nodes[-1].text(strip=True) if h1_nodes else slug

    rows = _profile_rows(parser)

    boat_type = None
    if (cells := rows.get("Type")) and len(cells) > 1:
        link = cells[1].css_first("a")
        boat_type = link.text(strip=True) if link else clean_text(cells[1]) or None

    builder = None
    laid_down = None
    if (cells := rows.get("Laid down")):
        if len(cells) > 1:
            laid_down = parse_date(cells[1].text(strip=True))
        if len(cells) > 2:
            link = cells[2].css_first("a")
            builder = link.text(strip=True) if link else clean_text(cells[2]) or None

    launched = None
    if (cells := rows.get("Launched")) and len(cells) > 1:
        launched = parse_date(cells[1].text(strip=True))

    commissioned = None
    if (cells := rows.get("Commissioned")) and len(cells) > 1:
        commissioned = parse_date(cells[1].text(strip=True))

    fate = None
    if (cells := rows.get("Fate")) and len(cells) > 1:
        fate = clean_text(cells[1]) or None

    return BoatData(
        slug=slug,
        number=number,
        type=boat_type,
        builder=builder,
        laid_down=laid_down,
        launched=launched,
        commissioned=commissioned,
        fate=fate,
    )


def fetch_boat(client: PoliteHttpClient, slug: str) -> BoatData:
    html = client.get_text(f"{BASE_URL}/boats/{slug}.htm")
    return parse_boat(html, slug)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_boat.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/scraping/uboat_net/boat.py tests/fixtures/uboat_net/u99.htm \
        tests/services/scraping/uboat_net/test_boat.py
git commit -m "Add uboat.net boat-detail scraper"
```

---

### Task 11: Patrol list scraper

**Files:**
- Create: `app/services/scraping/uboat_net/patrol_list.py`
- Create: `tests/fixtures/uboat_net/patrols_u99.html` (copied from a real fetch)
- Test: `tests/services/scraping/uboat_net/test_patrol_list.py`

**Interfaces:**
- Consumes: `PatrolSummary` (Task 3), `parse_date` (Task 3), `PoliteHttpClient`, `BASE_URL` (Task 8).
- Produces: `parse_patrol_list(html: str, page_url: str) -> list[PatrolSummary]`, `fetch_patrol_list(client: PoliteHttpClient, slug: str) -> list[PatrolSummary]`. Task 13 (`app/crawl.py`) calls `fetch_patrol_list` per boat, then Task 12's `fetch_patrol_detail` on each summary's `detail_url`.

- [ ] **Step 1: Copy the fixture**

```bash
cp /tmp/claude-1000/-home-scout-PycharmProjects-uboats/f70db281-1dd9-4e25-903a-d304ad9df26b/scratchpad/patrols_u99.html \
   tests/fixtures/uboat_net/patrols_u99.html
```

If unavailable, refetch once: `curl -s -A "uboats-scraper/0.1" "https://uboat.net/boats/patrols/u99.html" -o tests/fixtures/uboat_net/patrols_u99.html`.

- [ ] **Step 2: Write the failing test**

`tests/services/scraping/uboat_net/test_patrol_list.py`:

```python
from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.patrol_list import parse_patrol_list

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "patrols_u99.html"
_PAGE_URL = "https://uboat.net/boats/patrols/u99.html"


def test_parse_patrol_list_extracts_all_eight_patrols_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    summaries = parse_patrol_list(html, _PAGE_URL)

    assert len(summaries) == 8
    assert [s.patrol_number for s in summaries] == list(range(1, 9))


def test_parse_patrol_list_first_patrol_fields():
    html = _FIXTURE.read_text(encoding="utf-8")

    first = parse_patrol_list(html, _PAGE_URL)[0]

    assert first.external_id == "patrol_4754"
    assert first.commander == "Kptlt. Otto Kretschmer"
    assert first.departure_port == "Kiel"
    assert first.departure_date == date(1940, 6, 18)
    assert first.arrival_port == "Wilhelmshaven"
    assert first.arrival_date == date(1940, 6, 25)
    assert first.days_at_sea == 8
    assert first.tonnage is None
    assert first.detail_url == "https://uboat.net/boats/patrols/patrol_4754.html"


def test_parse_patrol_list_parses_tonnage_when_present():
    html = _FIXTURE.read_text(encoding="utf-8")

    second = parse_patrol_list(html, _PAGE_URL)[1]

    assert second.tonnage == 22719


def test_parse_patrol_list_stores_fate_text_as_arrival_port_when_boat_was_lost():
    html = _FIXTURE.read_text(encoding="utf-8")

    last = parse_patrol_list(html, _PAGE_URL)[-1]

    assert last.arrival_port == "Sunk"


def test_parse_patrol_list_missing_table_returns_empty_list():
    assert parse_patrol_list("<html><body>nothing here</body></html>", _PAGE_URL) == []
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_patrol_list.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `app/services/scraping/uboat_net/patrol_list.py`**

```python
import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_date
from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import PatrolSummary

_DAYS_RE = re.compile(r"(\d+)")


def parse_patrol_list(html: str, page_url: str) -> list[PatrolSummary]:
    parser = HTMLParser(html)
    table = parser.css_first("table.table_subtle")
    if table is None:
        return []

    summaries = []
    for row in table.css('tr[bgcolor="#f0f0f0"]'):
        cells = row.css("td")
        if len(cells) < 10:
            continue

        link = cells[9].css_first("a")
        if link is None:
            continue
        href = link.attributes.get("href") or ""
        detail_url = urljoin(page_url, href)
        external_id = href.rsplit("/", 1)[-1].removesuffix(".html")

        days_text = cells[6].text(strip=True)
        days_match = _DAYS_RE.match(days_text)

        tonnage_text = cells[7].text(strip=True)

        summaries.append(PatrolSummary(
            external_id=external_id,
            patrol_number=int(cells[0].text(strip=True) or 0),
            commander=clean_text(cells[1]) or None,
            departure_date=parse_date(cells[2].text(strip=True)),
            departure_port=cells[3].text(strip=True) or None,
            arrival_date=parse_date(cells[4].text(strip=True)),
            arrival_port=cells[5].text(strip=True) or None,
            days_at_sea=int(days_match.group(1)) if days_match else None,
            tonnage=int(tonnage_text.replace(",", "")) if tonnage_text else None,
            detail_url=detail_url,
        ))
    return summaries


def fetch_patrol_list(client: PoliteHttpClient, slug: str) -> list[PatrolSummary]:
    url = f"{BASE_URL}/boats/patrols/{slug}.html"
    html = client.get_text(url)
    return parse_patrol_list(html, url)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_patrol_list.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/scraping/uboat_net/patrol_list.py tests/fixtures/uboat_net/patrols_u99.html \
        tests/services/scraping/uboat_net/test_patrol_list.py
git commit -m "Add uboat.net patrol-list scraper"
```

---

### Task 12: Patrol detail (route) scraper

**Files:**
- Create: `app/services/scraping/uboat_net/patrol_detail.py`
- Create: `tests/fixtures/uboat_net/patrol_4754.html` (copied from a real fetch)
- Test: `tests/services/scraping/uboat_net/test_patrol_detail.py`

**Interfaces:**
- Consumes: `PatrolDetail`, `RoutePointData` (Task 3), `parse_iso_date` (Task 3), `clean_text` (Task 3), `PoliteHttpClient` (Task 8).
- Produces: `parse_patrol_detail(html: str) -> PatrolDetail`, `fetch_patrol_detail(client: PoliteHttpClient, url: str) -> PatrolDetail`. Task 13 (`app/crawl.py`) calls `fetch_patrol_detail` for every `PatrolSummary.detail_url`.

- [ ] **Step 1: Copy the fixture**

```bash
cp /tmp/claude-1000/-home-scout-PycharmProjects-uboats/f70db281-1dd9-4e25-903a-d304ad9df26b/scratchpad/patrol_4754.html \
   tests/fixtures/uboat_net/patrol_4754.html
```

If unavailable, refetch once: `curl -s -A "uboats-scraper/0.1" "https://uboat.net/boats/patrols/patrol_4754.html" -o tests/fixtures/uboat_net/patrol_4754.html`.

This fixture was already verified during design: `parsePatrolRouteCoordinates` contains exactly 11 `[lat, lng]` pairs, and there are exactly 11 `/boats/patrols/u99/YYYY-MM-DD.html` daily-position links in the same document order — confirmed with a real regex run against the live file before writing this plan.

- [ ] **Step 2: Write the failing test**

`tests/services/scraping/uboat_net/test_patrol_detail.py`:

```python
from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.patrol_detail import parse_patrol_detail

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "patrol_4754.html"


def test_parse_patrol_detail_extracts_all_route_points_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    detail = parse_patrol_detail(html)

    assert len(detail.route_points) == 11
    assert detail.route_points[0].sequence == 0
    assert detail.route_points[0].lat == 54.3667
    assert detail.route_points[0].lng == 10.1667
    assert detail.route_points[-1].lat == 53.5167
    assert detail.route_points[-1].lng == 8.15


def test_parse_patrol_detail_zips_dates_onto_route_points_in_order():
    html = _FIXTURE.read_text(encoding="utf-8")

    detail = parse_patrol_detail(html)

    assert detail.route_points[0].date == date(1940, 6, 18)
    assert detail.route_points[6].date == date(1940, 6, 24)
    assert detail.route_points[7].date == date(1940, 6, 25)
    assert detail.route_points[-1].date == date(1940, 6, 25)


def test_parse_patrol_detail_extracts_description():
    html = _FIXTURE.read_text(encoding="utf-8")

    detail = parse_patrol_detail(html)

    assert detail.description is not None
    assert "Left Germany for a patrol" in detail.description


def test_parse_patrol_detail_missing_route_script_returns_empty_points():
    detail = parse_patrol_detail("<div class='emphasis'><p>No map on this page.</p></div>")

    assert detail.route_points == []
    assert detail.description == "No map on this page."


def test_parse_patrol_detail_more_coordinates_than_dates_leaves_extra_points_undated():
    html = """
    <script>var patrolRouteCoordinates = [[1.0, 2.0],[3.0, 4.0]];</script>
    <a href="/boats/patrols/u1/1940-01-01.html">1 Jan 1940</a>
    """

    detail = parse_patrol_detail(html)

    assert len(detail.route_points) == 2
    assert detail.route_points[0].date == date(1940, 1, 1)
    assert detail.route_points[1].date is None
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_patrol_detail.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `app/services/scraping/uboat_net/patrol_detail.py`**

```python
import re

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_iso_date
from app.services.scraping.uboat_net.http_client import PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import PatrolDetail, RoutePointData

_COORDS_BLOCK_RE = re.compile(r"patrolRouteCoordinates\s*=\s*\[(.*?)\];", re.DOTALL)
_COORD_PAIR_RE = re.compile(r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]")
_DAILY_LINK_RE = re.compile(r'href="/boats/patrols/[^/"]+/(\d{4}-\d{2}-\d{2})\.html"')


def parse_patrol_detail(html: str) -> PatrolDetail:
    parser = HTMLParser(html)
    description_node = parser.css_first(".emphasis p")
    description = clean_text(description_node) or None if description_node else None

    coords_match = _COORDS_BLOCK_RE.search(html)
    coord_pairs = _COORD_PAIR_RE.findall(coords_match.group(1)) if coords_match else []
    dates = _DAILY_LINK_RE.findall(html)

    points = []
    for index, (lat, lng) in enumerate(coord_pairs):
        point_date = parse_iso_date(dates[index]) if index < len(dates) else None
        points.append(RoutePointData(sequence=index, lat=float(lat), lng=float(lng), date=point_date))

    return PatrolDetail(description=description, route_points=points)


def fetch_patrol_detail(client: PoliteHttpClient, url: str) -> PatrolDetail:
    html = client.get_text(url)
    return parse_patrol_detail(html)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `poetry run pytest tests/services/scraping/uboat_net/test_patrol_detail.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add app/services/scraping/uboat_net/patrol_detail.py tests/fixtures/uboat_net/patrol_4754.html \
        tests/services/scraping/uboat_net/test_patrol_detail.py
git commit -m "Add uboat.net patrol-detail scraper with dated route points"
```

---

### Task 13: Crawl orchestrator and CLI

**Files:**
- Create: `app/crawl.py`
- Test: `tests/test_crawl.py`

**Interfaces:**
- Consumes: `BoatRef`, `BoatData`, `PatrolSummary`, `PatrolDetail` (Task 3); `BoatRepository` (Task 5); `PatrolRepository` (Task 6); `BoatCrawlStateRepository` (Task 7); `PoliteHttpClient`, `build_user_agent`, `BASE_URL` (Task 8); `fetch_listing` (Task 9); `fetch_boat` (Task 10); `fetch_patrol_list` (Task 11); `fetch_patrol_detail` (Task 12); `create_engine`, `create_session_factory`, `init_models` (Task 2); `settings` (Task 1).
- Produces: `async def crawl_boats(boat_refs, session_factory, fetch_boat, fetch_patrol_list, fetch_patrol_detail, force=False) -> None` — the pure orchestration function, independently testable with fake fetch functions. `async def main(argv=None) -> None` — the CLI entrypoint used by `poetry run python -m app.crawl`.

- [ ] **Step 1: Write the failing test**

`tests/test_crawl.py`:

```python
from app.crawl import crawl_boats
from app.services.scraping.uboat_net.types import BoatData, BoatRef, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.patrol_repository import PatrolRepository


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return create_session_factory(engine)


def _boat_data(slug):
    return BoatData(
        slug=slug, number=slug.upper(), type="VIIB", builder=None,
        laid_down=None, launched=None, commissioned=None, fate=None,
    )


def _patrol_summary(slug):
    return PatrolSummary(
        external_id=f"patrol_{slug}", patrol_number=1, commander=None,
        departure_port=None, departure_date=None, arrival_port=None, arrival_date=None,
        days_at_sea=None, tonnage=None, detail_url=f"https://uboat.net/boats/patrols/patrol_{slug}.html",
    )


def _patrol_detail():
    return PatrolDetail(description="test patrol", route_points=[RoutePointData(0, 1.0, 2.0, None)])


async def test_crawl_boats_upserts_boat_and_patrol_and_records_success(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug="u99", number="U-99")]

    await crawl_boats(
        refs,
        session_factory,
        fetch_boat=lambda slug: _boat_data(slug),
        fetch_patrol_list=lambda slug: [_patrol_summary(slug)],
        fetch_patrol_detail=lambda url: _patrol_detail(),
    )

    async with session_factory() as session:
        summaries = await BoatRepository(session).list_summaries()
        routes = await PatrolRepository(session).list_routes()
        state = await BoatCrawlStateRepository(session).get("u99")

    assert len(summaries) == 1
    assert summaries[0].slug == "u99"
    assert len(routes) == 1
    assert len(routes[0].points) == 1
    assert state.status == "success"


async def test_crawl_boats_records_failure_and_continues_to_next_boat(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug="u1", number="U-1"), BoatRef(slug="u2", number="U-2")]

    def fetch_boat(slug):
        if slug == "u1":
            raise RuntimeError("network error")
        return _boat_data(slug)

    await crawl_boats(
        refs,
        session_factory,
        fetch_boat=fetch_boat,
        fetch_patrol_list=lambda slug: [],
        fetch_patrol_detail=lambda url: _patrol_detail(),
    )

    async with session_factory() as session:
        state_repo = BoatCrawlStateRepository(session)
        u1_state = await state_repo.get("u1")
        u2_state = await state_repo.get("u2")
        summaries = await BoatRepository(session).list_summaries()

    assert u1_state.status == "failed"
    assert "network error" in u1_state.last_error
    assert u2_state.status == "success"
    assert {s.slug for s in summaries} == {"u2"}


async def test_crawl_boats_skips_already_successful_boats_unless_forced(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug="u99", number="U-99")]
    calls = []

    def fetch_boat(slug):
        calls.append(slug)
        return _boat_data(slug)

    await crawl_boats(refs, session_factory, fetch_boat, lambda slug: [], lambda url: _patrol_detail())
    await crawl_boats(refs, session_factory, fetch_boat, lambda slug: [], lambda url: _patrol_detail())

    assert calls == ["u99"]

    await crawl_boats(
        refs, session_factory, fetch_boat, lambda slug: [], lambda url: _patrol_detail(), force=True,
    )

    assert calls == ["u99", "u99"]


async def test_crawl_boats_patrol_list_failure_records_boat_failure(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug="u99", number="U-99")]

    await crawl_boats(
        refs,
        session_factory,
        fetch_boat=lambda slug: _boat_data(slug),
        fetch_patrol_list=lambda slug: (_ for _ in ()).throw(RuntimeError("patrol list boom")),
        fetch_patrol_detail=lambda url: _patrol_detail(),
    )

    async with session_factory() as session:
        state = await BoatCrawlStateRepository(session).get("u99")

    assert state.status == "failed"
    assert "patrol list boom" in state.last_error
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `poetry run pytest tests/test_crawl.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.crawl'`.

- [ ] **Step 3: Write `app/crawl.py`**

```python
import argparse
import asyncio

from app.core.config import settings
from app.services.scraping.uboat_net.boat import fetch_boat
from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent
from app.services.scraping.uboat_net.listing import fetch_listing
from app.services.scraping.uboat_net.patrol_detail import fetch_patrol_detail
from app.services.scraping.uboat_net.patrol_list import fetch_patrol_list
from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.patrol_repository import PatrolRepository


async def crawl_boats(boat_refs, session_factory, fetch_boat, fetch_patrol_list, fetch_patrol_detail, force=False):
    for ref in boat_refs:
        if not force:
            async with session_factory() as session:
                existing = await BoatCrawlStateRepository(session).get(ref.slug)
            if existing is not None and existing.status == "success":
                continue

        try:
            boat_data = await asyncio.to_thread(fetch_boat, ref.slug)
            async with session_factory() as session:
                boat_repo = BoatRepository(session)
                await boat_repo.upsert_boat(boat_data)
                boat_id = await boat_repo.get_id_by_slug(ref.slug)

            summaries = await asyncio.to_thread(fetch_patrol_list, ref.slug)
            for summary in summaries:
                detail = await asyncio.to_thread(fetch_patrol_detail, summary.detail_url)
                async with session_factory() as session:
                    await PatrolRepository(session).upsert_patrol(boat_id, summary, detail)

            async with session_factory() as session:
                await BoatCrawlStateRepository(session).record_success(ref.slug)
        except Exception as exc:
            async with session_factory() as session:
                await BoatCrawlStateRepository(session).record_failure(ref.slug, str(exc))


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Crawl uboat.net for boats and patrol routes.")
    parser.add_argument("--limit", type=int, default=None, help="Crawl at most N boats from the listing.")
    parser.add_argument("--slugs", type=str, default=None, help="Comma-separated slugs to crawl, e.g. u99,u100.")
    parser.add_argument("--force", action="store_true", help="Re-crawl boats already marked successful.")
    parser.add_argument("--delay", type=float, default=None, help="Override CRAWL_DELAY_SECONDS.")
    return parser.parse_args(argv)


async def main(argv=None) -> None:
    args = _parse_args(argv)
    delay = args.delay if args.delay is not None else settings.CRAWL_DELAY_SECONDS

    engine = create_engine(settings.DATABASE_URL)
    await init_models(engine)
    session_factory = create_session_factory(engine)

    client = PoliteHttpClient(delay_seconds=delay, user_agent=build_user_agent(settings.CRAWLER_CONTACT))

    boat_refs = fetch_listing(client)
    if args.slugs:
        wanted = set(args.slugs.split(","))
        boat_refs = [ref for ref in boat_refs if ref.slug in wanted]
    if args.limit is not None:
        boat_refs = boat_refs[: args.limit]

    print(f"Crawling {len(boat_refs)} boat(s) with a {delay}s delay between requests...")

    await crawl_boats(
        boat_refs,
        session_factory,
        fetch_boat=lambda slug: fetch_boat(client, slug),
        fetch_patrol_list=lambda slug: fetch_patrol_list(client, slug),
        fetch_patrol_detail=lambda url: fetch_patrol_detail(client, url),
        force=args.force,
    )

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `poetry run pytest tests/test_crawl.py -v`
Expected: 4 passed. (These run fast — the fake `fetch_*` functions do no real I/O and no real sleeping.)

- [ ] **Step 5: Commit**

```bash
git add app/crawl.py tests/test_crawl.py
git commit -m "Add resumable async crawl orchestrator and CLI for app.crawl"
```

---

### Task 14: Query API endpoints

**Files:**
- Create: `app/core/database.py`
- Create: `app/http/api/uboats/boten_lijst.py`
- Create: `app/http/api/uboats/boot_detail.py`
- Create: `app/http/api/uboats/routes.py`
- Test: `tests/http/api/test_boten_lijst.py`
- Test: `tests/http/api/test_boot_detail.py`
- Test: `tests/http/api/test_routes.py`

**Interfaces:**
- Consumes: `BoatRepository` (Task 5), `PatrolRepository` (Task 6), `BoatSummary`/`BoatDetail`/`PatrolRouteOut` (Task 4), `create_engine`/`create_session_factory` (Task 2), `settings` (Task 1).
- Produces: three FastAPI `RequestHandler` classes discoverable by `RequestHandlerRegistry` (Task 1), and `app.core.database.engine` / `get_session_factory()` used by `app/main.py` (modified in Step 6 below).

- [ ] **Step 1: Write `app/core/database.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import injectable

from app.core.config import settings
from app.services.storage.database import create_engine, create_session_factory

engine = create_engine(settings.DATABASE_URL)
_session_factory = create_session_factory(engine)


@injectable
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory
```

- [ ] **Step 2: Write the failing tests**

`tests/http/api/test_boten_lijst.py`:

```python
from app.http.api.uboats.boten_lijst import RequestHandler
from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def test_handle_request_returns_boat_summaries(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(BoatData(
            slug="u99", number="U-99", type="VIIB", builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))

    result = await RequestHandler(session_factory).handle_request()

    assert len(result) == 1
    assert result[0].slug == "u99"

    await engine.dispose()
```

`tests/http/api/test_boot_detail.py`:

```python
import pytest
from fastapi import HTTPException

from app.http.api.uboats.boot_detail import RequestHandler
from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def test_handle_request_returns_boat_detail(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(BoatData(
            slug="u99", number="U-99", type="VIIB", builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))

    result = await RequestHandler(session_factory).handle_request("u99")

    assert result.slug == "u99"
    assert result.type == "VIIB"

    await engine.dispose()


async def test_handle_request_raises_404_for_unknown_slug(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    with pytest.raises(HTTPException) as exc_info:
        await RequestHandler(session_factory).handle_request("unknown")

    assert exc_info.value.status_code == 404

    await engine.dispose()
```

`tests/http/api/test_routes.py`:

```python
from app.http.api.uboats.routes import RequestHandler
from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.patrol_repository import PatrolRepository


async def test_handle_request_returns_patrol_routes(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        boat_repo = BoatRepository(session)
        await boat_repo.upsert_boat(BoatData(
            slug="u99", number="U-99", type=None, builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))
        boat_id = await boat_repo.get_id_by_slug("u99")
        summary = PatrolSummary(
            external_id="patrol_4754", patrol_number=1, commander=None,
            departure_port="Kiel", departure_date=None, arrival_port="Wilhelmshaven", arrival_date=None,
            days_at_sea=8, tonnage=None, detail_url="https://uboat.net/boats/patrols/patrol_4754.html",
        )
        detail = PatrolDetail(description=None, route_points=[RoutePointData(0, 54.3667, 10.1667, None)])
        await PatrolRepository(session).upsert_patrol(boat_id, summary, detail)

    result = await RequestHandler(session_factory).handle_request()

    assert len(result) == 1
    assert result[0].boat_slug == "u99"
    assert len(result[0].points) == 1

    await engine.dispose()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `poetry run pytest tests/http/api -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Write `app/http/api/uboats/boten_lijst.py`**

```python
from typing import Annotated

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import BoatSummary
from app.services.storage.boat_repository import BoatRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/boten", name="uboats_boten_lijst")
    async def handle_request(self) -> list[BoatSummary]:
        async with self.session_factory() as session:
            return await BoatRepository(session).list_summaries()
```

- [ ] **Step 5: Write `app/http/api/uboats/boot_detail.py`**

```python
from typing import Annotated

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import BoatDetail
from app.services.storage.boat_repository import BoatRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/boten/{slug}", name="uboats_boot_detail")
    async def handle_request(self, slug: str) -> BoatDetail:
        async with self.session_factory() as session:
            detail = await BoatRepository(session).get_detail(slug)
        if detail is None:
            raise HTTPException(status_code=404, detail="Boat not found")
        return detail
```

- [ ] **Step 6: Write `app/http/api/uboats/routes.py`**

```python
from typing import Annotated

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import PatrolRouteOut
from app.services.storage.patrol_repository import PatrolRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/routes", name="uboats_routes")
    async def handle_request(self) -> list[PatrolRouteOut]:
        async with self.session_factory() as session:
            return await PatrolRepository(session).list_routes()
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `poetry run pytest tests/http/api -v`
Expected: 4 passed.

- [ ] **Step 8: Wire the real app database into `app/main.py`**

Modify `app/main.py` (from Task 1) — add the imports and the `init_models` bootstrap call, right after the existing imports and before `app = FastAPI(...)`:

```python
import asyncio

import uvicorn
import wireup.integration.fastapi
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import settings
from app.core.container import container
from app.core.database import engine
from app.services.storage.database import init_models
from fastapi import FastAPI

asyncio.run(init_models(engine))

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    debug=settings.DEBUG,
)

with async_container_force_sync_scope(container) as scope:
    request_handler_registry = scope.get(RequestHandlerRegistry)
    handlers = list(request_handler_registry)

wireup.integration.fastapi.setup(container, app, class_based_handlers=handlers)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 9: Verify the app still boots with routes registered**

Run: `poetry run python -c "
import app.main
routes = sorted(r.path for r in app.main.app.routes if hasattr(r, 'path'))
print(routes)
"`
Expected: the printed list includes `/api/uboats/boten`, `/api/uboats/boten/{slug}`, `/api/uboats/routes` with no traceback.

- [ ] **Step 10: Commit**

```bash
git add app/core/database.py app/http/api/uboats/boten_lijst.py app/http/api/uboats/boot_detail.py \
        app/http/api/uboats/routes.py app/main.py tests/http/api
git commit -m "Add read-only query API for boats and patrol routes"
```

---

### Task 15: Manual end-to-end verification (10 boats)

Not a coded task — this is the real run the user asked for, and it's the strongest available check that the wireup/FastAPI wiring and the live site's markup match what Tasks 1–14 assumed.

- [ ] **Step 1: Run a 10-boat crawl**

Run: `cd /home/scout/PycharmProjects/uboats && poetry run python -m app.crawl --limit 10`
Expected: log lines showing "Crawling 10 boat(s) with a 10.0s delay between requests..." followed by "Done." after roughly 10 boats × (1 boat page + 1 patrol-list page + N patrol-detail pages) requests at 10s each — expect several minutes, not seconds, since this genuinely waits out the crawl-delay.

- [ ] **Step 2: Confirm the database has real data**

Run: `poetry run python -c "
import asyncio
from app.core.config import settings
from app.services.storage.database import create_engine, create_session_factory
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.patrol_repository import PatrolRepository

async def check():
    engine = create_engine(settings.DATABASE_URL)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        boats = await BoatRepository(session).list_summaries()
        routes = await PatrolRepository(session).list_routes()
    print(f'{len(boats)} boats, {len(routes)} patrol routes, {sum(len(r.points) for r in routes)} route points')
    await engine.dispose()

asyncio.run(check())
"`
Expected: `10 boats, N patrol routes, M route points` with N and M greater than 0 for at least some boats.

- [ ] **Step 3: Start the app and check the endpoints respond**

Run: `poetry run uvicorn app.main:app --port 8000 &` then, after a moment:
```bash
curl -s http://localhost:8000/api/uboats/boten | head -c 500
curl -s http://localhost:8000/api/uboats/routes | head -c 500
```
Expected: both return JSON arrays with real boat/route data, not errors. Stop the server afterward (`kill %1` or Ctrl+C).

- [ ] **Step 4: Report back**

Summarize to the user: how many boats/patrols/route points landed in the database, and confirm the three endpoints are serving real data — this is the "real 10 boats + working backend" checkpoint before starting the Leaflet frontend spec.

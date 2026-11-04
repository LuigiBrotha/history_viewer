import app.crawl as crawl
from app.crawl import crawl_boats, select_boats_to_crawl
from app.services.scraping.uboat_net.types import BoatData, BoatRef, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.crawl_status_repository import CrawlStatusRepository
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


async def test_select_boats_to_crawl_applies_limit_after_skipping_already_successful(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug=f"u{i}", number=f"U-{i}") for i in range(1, 5)]

    # First run "crawls" u1 and u2 successfully.
    await crawl_boats(
        refs[:2], session_factory,
        fetch_boat=lambda slug: _boat_data(slug),
        fetch_patrol_list=lambda slug: [],
        fetch_patrol_detail=lambda url: _patrol_detail(),
    )

    # A second invocation with --limit 2 should mean "2 boats that still need
    # it" (u3, u4), not silently re-select the already-successful u1/u2.
    selected = await select_boats_to_crawl(refs, session_factory, limit=2, force=False)

    assert [ref.slug for ref in selected] == ["u3", "u4"]


async def test_select_boats_to_crawl_with_force_ignores_status_and_limits_the_raw_listing(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug=f"u{i}", number=f"U-{i}") for i in range(1, 5)]

    await crawl_boats(
        refs[:2], session_factory,
        fetch_boat=lambda slug: _boat_data(slug),
        fetch_patrol_list=lambda slug: [],
        fetch_patrol_detail=lambda url: _patrol_detail(),
    )

    selected = await select_boats_to_crawl(refs, session_factory, limit=2, force=True)

    assert [ref.slug for ref in selected] == ["u1", "u2"]


async def test_select_boats_to_crawl_no_limit_returns_all_boats_needing_crawl(tmp_path):
    session_factory = await _session_factory(tmp_path)
    refs = [BoatRef(slug="u1", number="U-1"), BoatRef(slug="u2", number="U-2")]

    await crawl_boats(
        refs[:1], session_factory,
        fetch_boat=lambda slug: _boat_data(slug),
        fetch_patrol_list=lambda slug: [],
        fetch_patrol_detail=lambda url: _patrol_detail(),
    )

    selected = await select_boats_to_crawl(refs, session_factory, limit=None, force=False)

    assert [ref.slug for ref in selected] == ["u2"]


async def test_main_records_the_full_listing_size_before_limit_is_applied(tmp_path, monkeypatch):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    monkeypatch.setattr(crawl.settings, "DATABASE_URL", db_url)
    refs = [BoatRef(slug=f"u{n}", number=f"U-{n}") for n in range(1, 6)]
    monkeypatch.setattr(crawl, "fetch_listing", lambda client: refs)

    crawled = []

    async def fake_crawl_boats(boat_refs, *args, **kwargs):
        crawled.extend(boat_refs)

    monkeypatch.setattr(crawl, "crawl_boats", fake_crawl_boats)

    await crawl.main(["--limit", "2", "--slugs", "u1,u2,u3", "--delay", "0"])

    assert len(crawled) == 2
    engine = create_engine(db_url)
    async with create_session_factory(engine)() as session:
        status = await CrawlStatusRepository(session).get_status()
    await engine.dispose()
    assert status.listing_total == 5


def test_missing_routing_dependencies_disable_routing(monkeypatch, capsys):
    import sys
    monkeypatch.setitem(sys.modules, "app.routing_engine.water_router", None)

    assert crawl.load_route_leg() is None
    assert "routing" in capsys.readouterr().out.lower()

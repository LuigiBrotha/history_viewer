import asyncio
import sqlite3
from datetime import date, datetime, timezone

from sqlalchemy import update

from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.crawl_status_repository import CrawlStatusRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Patrol
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


async def test_upsert_patrol_sets_crawled_at_and_updated_at(tmp_path):
    from sqlalchemy import select

    from app.services.storage.models import Patrol

    session_factory = await _session_factory(tmp_path)
    detail = PatrolDetail(description=None, route_points=[])

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        await PatrolRepository(session).upsert_patrol(boat_id, _summary(), detail)
        first = (await session.execute(select(Patrol))).scalar_one()
        first_crawled, first_updated = first.crawled_at, first.updated_at
        assert first_crawled is not None and first_crawled.tzinfo is not None
        assert first_updated == first_crawled

        await PatrolRepository(session).upsert_patrol(boat_id, _summary(), detail)
        await session.refresh(first)
        assert first.crawled_at > first_crawled
        assert first.updated_at == first.crawled_at


CURSOR = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)


async def _seed_patrols_with_updated_at(session_factory, stamps):
    """Insert one patrol per (external_id, updated_at) pair and force its updated_at."""
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        for external_id, _ in stamps:
            await repo.upsert_patrol(boat_id, _summary(external_id), _detail())
        for external_id, stamp in stamps:
            await session.execute(
                update(Patrol).where(Patrol.external_id == external_id).values(updated_at=stamp)
            )
        await session.commit()


async def test_list_routes_since_returns_only_changed_patrols(tmp_path):
    session_factory = await _session_factory(tmp_path)
    await _seed_patrols_with_updated_at(session_factory, [
        ("older", datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)),
        ("newer", datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc)),
    ])

    async with session_factory() as session:
        routes = await PatrolRepository(session).list_routes(since=CURSOR)

    assert [r.external_id for r in routes] == ["newer"]


async def test_list_routes_since_includes_a_patrol_exactly_at_the_cursor(tmp_path):
    session_factory = await _session_factory(tmp_path)
    await _seed_patrols_with_updated_at(session_factory, [("exact", CURSOR)])

    async with session_factory() as session:
        routes = await PatrolRepository(session).list_routes(since=CURSOR)

    assert [r.external_id for r in routes] == ["exact"]


async def test_list_routes_since_excludes_patrols_without_a_timestamp(tmp_path):
    session_factory = await _session_factory(tmp_path)
    await _seed_patrols_with_updated_at(session_factory, [("legacy", None), ("fresh", CURSOR)])

    async with session_factory() as session:
        since_routes = await PatrolRepository(session).list_routes(since=CURSOR)
        all_routes = await PatrolRepository(session).list_routes()

    assert [r.external_id for r in since_routes] == ["fresh"]
    assert {r.external_id for r in all_routes} == {"legacy", "fresh"}


async def test_status_reads_while_another_connection_is_writing(tmp_path):
    session_factory = await _session_factory(tmp_path)
    db_path = f"{tmp_path}/test.db"

    writer = sqlite3.connect(db_path, isolation_level=None)
    writer.execute("BEGIN EXCLUSIVE")

    async def release_after_delay():
        await asyncio.sleep(0.2)
        writer.execute("COMMIT")
        writer.close()

    release = asyncio.create_task(release_after_delay())
    async with session_factory() as session:
        status = await CrawlStatusRepository(session).get_status()
    await release

    assert status.patrol_count == 0


async def test_water_routes_survive_a_recrawl_of_the_patrol(tmp_path):
    from app.services.routing.types import RoutedLeg
    from app.services.storage.water_route_repository import WaterRouteRepository

    factory = await _session_factory(tmp_path)
    points = [
        RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=51.0, lng=-4.0, date=date(1940, 6, 19)),
    ]
    async with factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(points))
        a, b = (50.0, -5.0), (51.0, -4.0)
        await WaterRouteRepository(session).save(a, b, RoutedLeg("ok", [a, b], 100.0))
        await repo.upsert_patrol(boat_id, _summary(), _detail(points))
        routes = await repo.list_routes()
    assert routes[0].legs[0].status == "ok"
    assert routes[0].legs[0].path == [[50.0, -5.0], [51.0, -4.0]]


async def test_list_routes_since_returns_legs_for_the_changed_patrols(tmp_path):
    from app.services.routing.types import RoutedLeg
    from app.services.storage.water_route_repository import WaterRouteRepository

    factory = await _session_factory(tmp_path)
    a, b = (50.0, -5.0), (51.0, -4.0)
    points = [
        RoutePointData(sequence=1, lat=a[0], lng=a[1], date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=b[0], lng=b[1], date=date(1940, 6, 19)),
    ]
    async with factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary("old"), _detail(points))
        await repo.upsert_patrol(boat_id, _summary("new", patrol_number=2), _detail(points))
        await WaterRouteRepository(session).save(a, b, RoutedLeg("ok", [a, b], 100.0))
        await session.execute(update(Patrol).where(Patrol.external_id == "old").values(
            updated_at=datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)))
        await session.execute(update(Patrol).where(Patrol.external_id == "new").values(
            updated_at=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc)))
        await session.commit()
        routes = await repo.list_routes(since=datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc))
    assert [route.external_id for route in routes] == ["new"]
    assert [(leg.status, leg.path) for leg in routes[0].legs] == [("ok", [[50.0, -5.0], [51.0, -4.0]])]


async def test_a_single_point_patrol_has_no_legs(tmp_path):
    factory = await _session_factory(tmp_path)
    async with factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        points = [RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=date(1940, 6, 18))]
        await repo.upsert_patrol(boat_id, _summary(), _detail(points))
        routes = await repo.list_routes()
    assert routes[0].legs == []

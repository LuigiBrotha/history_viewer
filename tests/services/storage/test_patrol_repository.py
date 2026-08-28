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

from datetime import datetime, timezone

from sqlalchemy import select, update

from app.compute_water_routes import backfill, compute_routes_for_points
from app.crawl import crawl_boats
from app.services.routing.types import RoutedLeg
from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.scraping.uboat_net.types import BoatRef
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Patrol
from app.services.storage.patrol_repository import PatrolRepository
from app.services.storage.water_route_repository import WaterRouteRepository


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return create_session_factory(engine)


def _boat(slug):
    return BoatData(slug=slug, number=slug.upper(), type="VIIB", builder=None,
                    laid_down=None, launched=None, commissioned=None, fate=None)


def _summary(slug):
    return PatrolSummary(
        external_id=f"patrol_{slug}", patrol_number=1, commander=None, departure_port=None,
        departure_date=None, arrival_port=None, arrival_date=None, days_at_sea=None,
        tonnage=None, detail_url=f"https://uboat.net/{slug}.html",
    )


def _detail(*coords):
    return PatrolDetail(description="d", route_points=[
        RoutePointData(i, lat, lng, None) for i, (lat, lng) in enumerate(coords)
    ])


def _fake_route_leg(calls=None):
    def route_leg(start, end):
        if calls is not None:
            calls.append((start, end))
        return RoutedLeg("ok", [start, end], 1.0)
    return route_leg


async def _seed(session_factory, *coords):
    await crawl_boats(
        [BoatRef(slug="u1", number="U-1")], session_factory,
        fetch_boat=_boat, fetch_patrol_list=lambda s: [_summary(s)],
        fetch_patrol_detail=lambda url: _detail(*coords),
    )


async def _stored(session_factory, pairs):
    async with session_factory() as session:
        return await WaterRouteRepository(session).get_many(pairs)


async def _patrol_times(session_factory):
    async with session_factory() as session:
        row = (await session.execute(select(Patrol))).scalars().one()
        return row.crawled_at, row.updated_at


async def test_crawl_stores_routes_before_the_patrol_appears(tmp_path):
    session_factory = await _session_factory(tmp_path)
    seen = []

    def route_leg(start, end):
        seen.append(start)
        return RoutedLeg("ok", [start, end], 1.0)

    await crawl_boats(
        [BoatRef(slug="u1", number="U-1")], session_factory,
        fetch_boat=_boat, fetch_patrol_list=lambda s: [_summary(s)],
        fetch_patrol_detail=lambda url: _detail((1.0, 2.0), (3.0, 4.0), (5.0, 6.0)),
        route_leg=route_leg,
    )

    assert seen == [(1.0, 2.0), (3.0, 4.0)]
    async with session_factory() as session:
        routes = await PatrolRepository(session).list_routes()
    assert [leg.status for leg in routes[0].legs] == ["ok", "ok"]


async def test_routing_failure_does_not_fail_the_crawl(tmp_path, capsys):
    session_factory = await _session_factory(tmp_path)

    def route_leg(start, end):
        raise RuntimeError("boom")

    await crawl_boats(
        [BoatRef(slug="u1", number="U-1")], session_factory,
        fetch_boat=_boat, fetch_patrol_list=lambda s: [_summary(s)],
        fetch_patrol_detail=lambda url: _detail((1.0, 2.0), (3.0, 4.0)),
        route_leg=route_leg,
    )

    async with session_factory() as session:
        routes = await PatrolRepository(session).list_routes()
    assert len(routes) == 1
    assert "boom" in capsys.readouterr().out


async def test_backfill_skips_stored_pairs_unless_forced(tmp_path):
    session_factory = await _session_factory(tmp_path)
    await _seed(session_factory, (1.0, 2.0), (3.0, 4.0), (1.0, 2.0), (3.0, 4.0))
    calls = []

    await backfill(session_factory, _fake_route_leg(calls))
    assert calls == [((1.0, 2.0), (3.0, 4.0)), ((3.0, 4.0), (1.0, 2.0))]

    calls.clear()
    await backfill(session_factory, _fake_route_leg(calls))
    assert calls == []

    await backfill(session_factory, _fake_route_leg(calls), force=True)
    assert len(calls) == 2


async def test_backfill_bumps_updated_at_but_not_crawled_at(tmp_path):
    session_factory = await _session_factory(tmp_path)
    await _seed(session_factory, (1.0, 2.0), (3.0, 4.0))
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    async with session_factory() as session:
        await session.execute(update(Patrol).values(crawled_at=old, updated_at=old))
        await session.commit()

    await backfill(session_factory, _fake_route_leg())
    crawled, updated = await _patrol_times(session_factory)
    assert crawled == old
    assert updated > old

    async with session_factory() as session:
        await session.execute(update(Patrol).values(updated_at=old))
        await session.commit()
    await backfill(session_factory, _fake_route_leg())
    assert (await _patrol_times(session_factory))[1] == old


async def test_backfill_continues_after_a_failing_leg(tmp_path, capsys):
    session_factory = await _session_factory(tmp_path)
    points = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]

    def route_leg(start, end):
        if start == (1.0, 2.0):
            raise RuntimeError("bad leg")
        return RoutedLeg("ok", [start, end], 1.0)

    class P:
        def __init__(self, lat, lng):
            self.lat, self.lng = lat, lng

    await compute_routes_for_points([P(*c) for c in points], session_factory, route_leg)

    stored = await _stored(session_factory, [(points[0], points[1]), (points[1], points[2])])
    assert list(stored) == [(points[1], points[2])]
    assert "bad leg" in capsys.readouterr().out


async def test_repository_failure_does_not_propagate(tmp_path, monkeypatch, capsys):
    session_factory = await _session_factory(tmp_path)

    async def broken(self, pairs, force=False):
        raise RuntimeError("db down")

    monkeypatch.setattr(WaterRouteRepository, "missing", broken)

    class P:
        lat, lng = 1.0, 2.0

    n = await compute_routes_for_points([P(), P()], session_factory, _fake_route_leg())
    assert n == 0
    assert "db down" in capsys.readouterr().out

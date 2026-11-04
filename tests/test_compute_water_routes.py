from datetime import datetime, timezone

from sqlalchemy import select, update

from app import compute_water_routes
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


async def _seed_two_boats(session_factory, details):
    await crawl_boats(
        [BoatRef(slug="u1", number="U-1"), BoatRef(slug="u2", number="U-2")], session_factory,
        fetch_boat=_boat, fetch_patrol_list=lambda s: [_summary(s)],
        fetch_patrol_detail=lambda url: _detail(*details[url]),
    )


async def _updated_at(session_factory):
    async with session_factory() as session:
        rows = (await session.execute(select(Patrol.external_id, Patrol.updated_at))).all()
    return dict(rows)


async def _age_patrols(session_factory, old):
    async with session_factory() as session:
        await session.execute(update(Patrol).values(crawled_at=old, updated_at=old))
        await session.commit()


async def test_backfill_touches_a_patrol_whose_legs_were_computed_for_an_earlier_patrol(tmp_path):
    session_factory = await _session_factory(tmp_path)
    shared = [(1.0, 2.0), (3.0, 4.0)]
    await _seed_two_boats(session_factory, {
        "https://uboat.net/u1.html": shared, "https://uboat.net/u2.html": shared,
    })
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    await _age_patrols(session_factory, old)

    await backfill(session_factory, _fake_route_leg())
    assert all(stamp > old for stamp in (await _updated_at(session_factory)).values())

    await _age_patrols(session_factory, old)
    await backfill(session_factory, _fake_route_leg())
    assert set((await _updated_at(session_factory)).values()) == {old}


async def test_backfill_survives_a_failing_point_read_or_touch_and_reports_counts(tmp_path, monkeypatch, capsys):
    session_factory = await _session_factory(tmp_path)
    await _seed_two_boats(session_factory, {
        "https://uboat.net/u1.html": [(1.0, 2.0), (3.0, 4.0)],
        "https://uboat.net/u2.html": [(5.0, 6.0), (7.0, 8.0), (9.0, 10.0)],
    })
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    await _age_patrols(session_factory, old)
    real_read = compute_water_routes._read_points

    async def read_points(factory, patrol_id):
        if patrol_id == 1:
            raise RuntimeError("read down")
        return await real_read(factory, patrol_id)

    async def touch(self, external_id):
        raise RuntimeError("touch down")

    def route_leg(start, end):
        if start == (7.0, 8.0):
            raise RuntimeError("bad leg")
        return RoutedLeg("ok", [start, end], 1.0)

    monkeypatch.setattr(compute_water_routes, "_read_points", read_points)
    monkeypatch.setattr(PatrolRepository, "touch", touch)

    await backfill(session_factory, route_leg)

    out = capsys.readouterr().out
    assert "read down" in out and "touch down" in out and "bad leg" in out
    assert "1 legen mislukt" in out
    assert "1 legen nog niet berekend" in out
    assert await _stored(session_factory, [((5.0, 6.0), (7.0, 8.0))])


async def _exclude(session_factory, external_id, sequence):
    async with session_factory() as session:
        await PatrolRepository(session).exclude_point(external_id, sequence)


async def test_backfill_computes_the_leg_across_an_excluded_point(tmp_path):
    session_factory = await _session_factory(tmp_path)
    a, b, c = (1.0, 2.0), (3.0, 4.0), (5.0, 6.0)
    await _seed(session_factory, a, b, c)
    await _exclude(session_factory, "patrol_u1", 1)

    await backfill(session_factory, _fake_route_leg())

    assert set(await _stored(session_factory, [(a, b), (b, c), (a, c)])) == {(a, b), (b, c), (a, c)}


async def test_backfill_counts_an_uncomputed_leg_across_an_excluded_point(tmp_path, capsys):
    session_factory = await _session_factory(tmp_path)
    a, b, c = (1.0, 2.0), (3.0, 4.0), (5.0, 6.0)
    await _seed(session_factory, a, b, c)
    await _exclude(session_factory, "patrol_u1", 1)

    def route_leg(start, end):
        if (start, end) == (a, c):
            raise RuntimeError("bad shortcut")
        return RoutedLeg("ok", [start, end], 1.0)

    await backfill(session_factory, route_leg)

    out = capsys.readouterr().out
    assert "1 legen mislukt" in out
    assert "1 legen nog niet berekend" in out

    # A later run, with routing working again, fills the gap.
    await backfill(session_factory, _fake_route_leg())
    assert (a, c) in await _stored(session_factory, [(a, c)])
    assert "0 legen nog niet berekend" in capsys.readouterr().out


async def test_crawl_computes_the_leg_across_an_excluded_point_after_the_upsert(tmp_path):
    session_factory = await _session_factory(tmp_path)
    a, b, c = (1.0, 2.0), (3.0, 4.0), (5.0, 6.0)
    await _seed(session_factory, a, b, c)
    await _exclude(session_factory, "patrol_u1", 1)

    await crawl_boats(
        [BoatRef(slug="u1", number="U-1")], session_factory,
        fetch_boat=_boat, fetch_patrol_list=lambda s: [_summary(s)],
        fetch_patrol_detail=lambda url: _detail(a, b, c),
        route_leg=_fake_route_leg(), force=True,
    )

    assert (a, c) in await _stored(session_factory, [(a, c)])

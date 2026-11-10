import asyncio
import sqlite3
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select, update

from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.crawl_status_repository import CrawlStatusRepository
from app.services.storage.models import ExcludedRoutePoint, Patrol, RoutePoint
from app.services.storage.patrol_repository import PatrolRepository


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


async def test_upsert_patrol_inserts_patrol_and_route_points(session_factory):

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


async def test_upsert_patrol_replaces_route_points_on_conflict(session_factory):

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


async def test_upsert_patrol_updates_summary_fields_on_conflict(session_factory):

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(tonnage=None), _detail())
        await repo.upsert_patrol(boat_id, _summary(tonnage=22719), _detail())
        detail = await BoatRepository(session).get_detail("u99")

    assert detail.patrols[0].tonnage == 22719


async def test_list_routes_orders_by_boat_slug_then_patrol_number(session_factory):

    async with session_factory() as session:
        boat_a = await _seed_boat(session, slug="u100", number="U-100")
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_a, _summary(external_id="patrol_2", patrol_number=2), _detail())
        await repo.upsert_patrol(boat_a, _summary(external_id="patrol_1", patrol_number=1), _detail())
        routes = await repo.list_routes()

    assert [r.external_id for r in routes] == ["patrol_1", "patrol_2"]


async def test_upsert_patrol_sets_crawled_at_and_updated_at(session_factory):
    from sqlalchemy import select

    from app.services.storage.models import Patrol

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


async def test_list_routes_since_returns_only_changed_patrols(session_factory):
    await _seed_patrols_with_updated_at(session_factory, [
        ("older", datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)),
        ("newer", datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc)),
    ])

    async with session_factory() as session:
        routes = await PatrolRepository(session).list_routes(since=CURSOR)

    assert [r.external_id for r in routes] == ["newer"]


async def test_list_routes_since_includes_a_patrol_exactly_at_the_cursor(session_factory):
    await _seed_patrols_with_updated_at(session_factory, [("exact", CURSOR)])

    async with session_factory() as session:
        routes = await PatrolRepository(session).list_routes(since=CURSOR)

    assert [r.external_id for r in routes] == ["exact"]


async def test_list_routes_since_excludes_patrols_without_a_timestamp(session_factory):
    await _seed_patrols_with_updated_at(session_factory, [("legacy", None), ("fresh", CURSOR)])

    async with session_factory() as session:
        since_routes = await PatrolRepository(session).list_routes(since=CURSOR)
        all_routes = await PatrolRepository(session).list_routes()

    assert [r.external_id for r in since_routes] == ["fresh"]
    assert {r.external_id for r in all_routes} == {"legacy", "fresh"}


async def test_status_reads_while_another_connection_is_writing(tmp_path, session_factory):
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


async def test_water_routes_survive_a_recrawl_of_the_patrol(session_factory):
    from app.services.routing.types import RoutedLeg
    from app.services.storage.water_route_repository import WaterRouteRepository

    points = [
        RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=51.0, lng=-4.0, date=date(1940, 6, 19)),
    ]
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(points))
        a, b = (50.0, -5.0), (51.0, -4.0)
        await WaterRouteRepository(session).save(a, b, RoutedLeg("ok", [a, b], 100.0))
        await repo.upsert_patrol(boat_id, _summary(), _detail(points))
        routes = await repo.list_routes()
    assert routes[0].legs[0].status == "ok"
    assert routes[0].legs[0].path == [[50.0, -5.0], [51.0, -4.0]]


async def test_list_routes_since_returns_legs_for_the_changed_patrols(session_factory):
    from app.services.routing.types import RoutedLeg
    from app.services.storage.water_route_repository import WaterRouteRepository

    a, b = (50.0, -5.0), (51.0, -4.0)
    points = [
        RoutePointData(sequence=1, lat=a[0], lng=a[1], date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=b[0], lng=b[1], date=date(1940, 6, 19)),
    ]
    async with session_factory() as session:
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


async def test_a_single_point_patrol_has_no_legs(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        points = [RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=date(1940, 6, 18))]
        await repo.upsert_patrol(boat_id, _summary(), _detail(points))
        routes = await repo.list_routes()
    assert routes[0].legs == []


async def test_list_routes_approximates_dates_without_storing_them(tmp_path, session_factory):
    from app.services.routing.types import RoutedLeg
    from app.services.storage.water_route_repository import WaterRouteRepository

    points = [RoutePointData(0, 50.0, -20.0, None), RoutePointData(1, 60.0, 20.0, None)]
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        await PatrolRepository(session).upsert_patrol(
            boat_id,
            _summary(departure_date=date(1940, 1, 1), arrival_date=date(1940, 1, 3)),
            _detail(points),
        )
        # 2000 km over 2 approximated days would look suspect if days were derived from them.
        await WaterRouteRepository(session).save(
            (50.0, -20.0), (60.0, 20.0), RoutedLeg("ok", [(50.0, -20.0), (60.0, 20.0)], 2000.0)
        )

    async with session_factory() as session:
        route = (await PatrolRepository(session).list_routes())[0]

    assert [p.date for p in route.points] == [date(1940, 1, 1), date(1940, 1, 3)]
    assert all(p.date_approximate for p in route.points)
    assert route.legs[0].status == "ok"
    assert route.legs[0].days is None

    connection = sqlite3.connect(f"{tmp_path}/test.db")
    assert connection.execute("select date from route_points").fetchall() == [(None,), (None,)]
    connection.close()


async def test_list_routes_keeps_known_dates_exact(session_factory):
    points = [RoutePointData(0, 50.0, -20.0, date(1940, 1, 2))]
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        await PatrolRepository(session).upsert_patrol(
            boat_id,
            _summary(departure_date=date(1940, 1, 1), arrival_date=date(1940, 1, 3)),
            _detail(points),
        )

    async with session_factory() as session:
        route = (await PatrolRepository(session).list_routes())[0]

    assert route.points[0].date == date(1940, 1, 2)
    assert route.points[0].date_approximate is False


def _three_points(middle_date=date(1940, 6, 19)):
    return [
        RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=51.0, lng=-4.0, date=middle_date),
        RoutePointData(sequence=3, lat=52.0, lng=-3.0, date=date(1940, 6, 20)),
    ]


async def test_excluded_point_leaves_points_and_joins_excluded_points(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        assert await repo.exclude_point("patrol_4754", 2) == (51.0, -4.0)
        routes = await repo.list_routes()
        await repo.restore_point("patrol_4754", 2)
        restored = await repo.list_routes()
    assert [p.sequence for p in routes[0].points] == [1, 3]
    assert [(p.sequence, p.lat, p.lng, p.date) for p in routes[0].excluded_points] == [
        (2, 51.0, -4.0, date(1940, 6, 19))]
    assert [p.sequence for p in restored[0].points] == [1, 2, 3]
    assert restored[0].excluded_points == []


async def test_legs_connect_the_neighbours_of_an_excluded_point(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await repo.exclude_point("patrol_4754", 2)
        routes = await repo.list_routes()
    assert [(leg.from_sequence, leg.to_sequence) for leg in routes[0].legs] == [(1, 3)]


async def test_exclusion_survives_a_recrawl_with_new_sequences(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await repo.exclude_point("patrol_4754", 2)
        shifted = [
            RoutePointData(sequence=10, lat=49.0, lng=-6.0, date=date(1940, 6, 17)),
            RoutePointData(sequence=11, lat=50.0, lng=-5.0, date=date(1940, 6, 18)),
            RoutePointData(sequence=12, lat=51.0, lng=-4.0, date=date(1940, 6, 19)),
            RoutePointData(sequence=13, lat=52.0, lng=-3.0, date=date(1940, 6, 20)),
        ]
        await repo.upsert_patrol(boat_id, _summary(), _detail(shifted))
        routes = await repo.list_routes()
    assert [p.sequence for p in routes[0].points] == [10, 11, 13]
    assert [p.sequence for p in routes[0].excluded_points] == [12]


async def test_undated_point_can_be_excluded_and_restored(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points(middle_date=None)))
        await repo.exclude_point("patrol_4754", 2)
        excluded = await repo.list_routes()
        await repo.restore_point("patrol_4754", 2)
        restored = await repo.list_routes()
    assert [p.sequence for p in excluded[0].excluded_points] == [2]
    assert excluded[0].excluded_points[0].date is None
    assert [p.sequence for p in restored[0].points] == [1, 2, 3]


async def test_excluding_the_only_remaining_point_is_refused(session_factory):
    from app.services.storage.patrol_repository import LastPointError

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary("one"), _detail(
            [RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=None)]))
        await repo.upsert_patrol(boat_id, _summary("two", patrol_number=2), _detail(_three_points()))
        with pytest.raises(LastPointError):
            await repo.exclude_point("one", 1)
        await repo.exclude_point("two", 1)
        await repo.exclude_point("two", 2)
        with pytest.raises(LastPointError):
            await repo.exclude_point("two", 3)


async def test_unknown_patrol_or_sequence_is_not_found(session_factory):
    from app.services.storage.patrol_repository import PatrolNotFound, PointNotFound

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        with pytest.raises(PatrolNotFound):
            await repo.exclude_point("nope", 1)
        with pytest.raises(PatrolNotFound):
            await repo.restore_point("nope", 1)
        with pytest.raises(PointNotFound):
            await repo.exclude_point("patrol_4754", 99)
        with pytest.raises(PointNotFound):
            await repo.restore_point("patrol_4754", 99)
        await repo.restore_point("patrol_4754", 2)  # not excluded: no-op


async def test_exclude_and_restore_bump_updated_at(session_factory):
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await session.execute(update(Patrol).values(updated_at=old))
        await session.commit()
        crawled = (await session.scalar(select(Patrol.crawled_at)))
        await repo.exclude_point("patrol_4754", 2)
        after_exclude = await session.scalar(select(Patrol.updated_at))
        await session.execute(update(Patrol).values(updated_at=old))
        await session.commit()
        await repo.restore_point("patrol_4754", 2)
        after_restore = await session.scalar(select(Patrol.updated_at))
        assert await session.scalar(select(Patrol.crawled_at)) == crawled
    assert after_exclude > old
    assert after_restore > old


async def test_source_route_point_row_is_untouched(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await repo.exclude_point("patrol_4754", 2)
        rows = (await session.scalars(select(RoutePoint).order_by(RoutePoint.sequence))).all()
    assert [r.sequence for r in rows] == [1, 2, 3]


async def test_exclusion_survives_a_recrawl_that_loses_the_date(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await repo.exclude_point("patrol_4754", 2)
        recrawled = [
            RoutePointData(sequence=10, lat=50.0, lng=-5.0, date=date(1940, 6, 18)),
            RoutePointData(sequence=11, lat=51.0, lng=-4.0, date=None),
            RoutePointData(sequence=12, lat=52.0, lng=-3.0, date=date(1940, 6, 20)),
        ]
        await repo.upsert_patrol(boat_id, _summary(), _detail(recrawled))
        routes = await repo.list_routes()
    assert [p.sequence for p in routes[0].points] == [10, 12]
    assert [p.sequence for p in routes[0].excluded_points] == [11]


def _duplicate_points():
    return [
        RoutePointData(sequence=1, lat=50.0, lng=-5.0, date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=51.0, lng=-4.0, date=date(1940, 6, 19)),
        RoutePointData(sequence=3, lat=51.0, lng=-4.0, date=date(1940, 6, 20)),
    ]


async def test_excluding_one_of_two_twins_keeps_the_other(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_duplicate_points()))
        await repo.exclude_point("patrol_4754", 2)
        excluded = await repo.list_routes()
    assert [p.sequence for p in excluded[0].points] == [1, 3]
    assert [p.sequence for p in excluded[0].excluded_points] == [2]


async def test_excluding_the_first_home_port_point_keeps_the_last(session_factory):
    home = [
        RoutePointData(sequence=1, lat=54.0, lng=10.0, date=date(1940, 6, 18)),
        RoutePointData(sequence=2, lat=56.0, lng=5.0, date=date(1940, 6, 19)),
        RoutePointData(sequence=3, lat=54.0, lng=10.0, date=date(1940, 6, 25)),
    ]
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(home))
        await repo.exclude_point("patrol_4754", 1)
        routes = await repo.list_routes()
    assert [p.sequence for p in routes[0].points] == [2, 3]
    assert [p.sequence for p in routes[0].excluded_points] == [1]


async def test_restoring_one_twin_leaves_the_other_excluded(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_duplicate_points()))
        await repo.exclude_point("patrol_4754", 2)
        await repo.exclude_point("patrol_4754", 3)
        both = await repo.list_routes()
        await repo.restore_point("patrol_4754", 3)
        restored = await repo.list_routes()
    assert [p.sequence for p in both[0].points] == [1]
    assert [p.sequence for p in restored[0].points] == [1, 3]
    assert [p.sequence for p in restored[0].excluded_points] == [2]


async def test_a_twin_exclusion_survives_a_recrawl_with_shifted_sequences(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_duplicate_points()))
        await repo.exclude_point("patrol_4754", 3)
        recrawled = [
            RoutePointData(sequence=10, lat=50.0, lng=-5.0, date=None),
            RoutePointData(sequence=11, lat=51.0, lng=-4.0, date=None),
            RoutePointData(sequence=12, lat=51.0, lng=-4.0, date=None),
        ]
        await repo.upsert_patrol(boat_id, _summary(), _detail(recrawled))
        routes = await repo.list_routes()
    assert [p.sequence for p in routes[0].points] == [10, 11]
    assert [p.sequence for p in routes[0].excluded_points] == [12]


async def test_last_point_error_counts_visible_rows(session_factory):
    from app.services.storage.patrol_repository import LastPointError

    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_duplicate_points()))
        await repo.exclude_point("patrol_4754", 1)
        await repo.exclude_point("patrol_4754", 2)
        with pytest.raises(LastPointError):
            await repo.exclude_point("patrol_4754", 3)
        routes = await repo.list_routes()
    assert [p.sequence for p in routes[0].points] == [3]


async def test_excluding_twice_is_idempotent(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await repo.exclude_point("patrol_4754", 2)
        assert await repo.exclude_point("patrol_4754", 2) == (51.0, -4.0)
        routes = await repo.list_routes()
        stored = (await session.scalars(select(ExcludedRoutePoint))).all()
    assert [p.sequence for p in routes[0].excluded_points] == [2]
    assert len(stored) == 1


async def test_since_listing_includes_excluded_points(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(), _detail(_three_points()))
        await repo.exclude_point("patrol_4754", 2)
        routes = await repo.list_routes(since=datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert [p.sequence for p in routes[0].points] == [1, 3]
    assert [p.sequence for p in routes[0].excluded_points] == [2]


async def test_excluding_a_point_respreads_approximate_dates_over_the_rest(session_factory):
    undated = [RoutePointData(sequence=i, lat=50.0 + i, lng=-5.0, date=None) for i in range(1, 6)]
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        repo = PatrolRepository(session)
        await repo.upsert_patrol(boat_id, _summary(arrival_date=date(1940, 6, 22)), _detail(undated))
        before = await repo.list_routes()
        await repo.exclude_point("patrol_4754", 3)
        after = await repo.list_routes()
    assert [p.date for p in before[0].points] == [date(1940, 6, d) for d in (18, 19, 20, 21, 22)]
    assert [p.sequence for p in after[0].points] == [1, 2, 4, 5]
    assert [p.date for p in after[0].points] == [date(1940, 6, d) for d in (18, 19, 21, 22)]
    assert all(p.date_approximate for p in after[0].points)
    assert after[0].excluded_points[0].date is None


async def _seed_three_patrols(session_factory):
    async with session_factory() as session:
        boat_id = await _seed_boat(session)
        for number in (1, 2, 3):
            await PatrolRepository(session).upsert_patrol(
                boat_id, _summary(f"patrol_{number}", patrol_number=number), _detail()
            )


async def test_list_routes_returns_a_page(session_factory):
    await _seed_three_patrols(session_factory)

    async with session_factory() as session:
        repo = PatrolRepository(session)
        first = await repo.list_routes(limit=2, offset=0)
        second = await repo.list_routes(limit=2, offset=2)

    assert [r.external_id for r in first] == ["patrol_1", "patrol_2"]
    assert [r.external_id for r in second] == ["patrol_3"]

from app.services.routing.types import RoutedLeg
from app.services.storage import water_route_repository
from app.services.storage.water_route_repository import WaterRouteRepository

A = (50.0, -5.0)
B = (51.0, -4.0)
C = (52.0, -3.0)


async def test_save_and_get_many_round_trip(session_factory):
    async with session_factory() as session:
        repo = WaterRouteRepository(session)
        await repo.save(A, B, RoutedLeg("ok", [A, (50.5, -4.5), B], 123.4))
        await repo.save(B, C, RoutedLeg("on_land", None, None))
        got = await repo.get_many([(A, B), (B, C), (A, C)])
    assert got == {
        (A, B): RoutedLeg("ok", [A, (50.5, -4.5), B], 123.4),
        (B, C): RoutedLeg("on_land", None, None),
    }


async def test_save_upserts(session_factory):
    async with session_factory() as session:
        repo = WaterRouteRepository(session)
        await repo.save(A, B, RoutedLeg("no_route", None, None))
        await repo.save(A, B, RoutedLeg("ok", [A, B], 5.0))
        got = await repo.get_many([(A, B)])
    assert got[(A, B)] == RoutedLeg("ok", [A, B], 5.0)


async def test_get_many_chunks_large_inputs(session_factory):
    pairs = [((float(i), 0.0), (float(i), 1.0)) for i in range(2000)]
    async with session_factory() as session:
        repo = WaterRouteRepository(session)
        await repo.save(*pairs[1999], RoutedLeg("ok", [pairs[1999][0], pairs[1999][1]], 1.0))
        got = await repo.get_many(pairs)
    assert list(got) == [pairs[1999]]


async def test_missing_dedupes_keeps_order_and_honours_force(session_factory):
    async with session_factory() as session:
        repo = WaterRouteRepository(session)
        await repo.save(A, B, RoutedLeg("ok", [A, B], 1.0))
        pairs = [(B, C), (A, B), (B, C), (A, C)]
        assert await repo.missing(pairs) == [(B, C), (A, C)]
        assert await repo.missing(pairs, force=True) == [(B, C), (A, B), (A, C)]


async def test_get_many_reads_the_whole_table_above_the_threshold(monkeypatch, session_factory):
    stored = {
        (A, B): RoutedLeg("ok", [A, (50.5, -4.5), B], 123.4),
        (B, C): RoutedLeg("on_land", None, None),
        (A, C): RoutedLeg("no_route", None, None),
    }
    async with session_factory() as session:
        repo = WaterRouteRepository(session)
        for pair, leg in stored.items():
            await repo.save(*pair, leg)
        asked = [(A, B), (B, C), (C, A), (A, B)]
        chunked = await repo.get_many(asked)

        monkeypatch.setattr(water_route_repository, "FULL_READ_THRESHOLD", 2)
        monkeypatch.setattr(water_route_repository, "LATITUDE_CHUNK_SIZE", 1)
        full = await repo.get_many(asked)

    assert chunked == full == {(A, B): stored[(A, B)], (B, C): stored[(B, C)]}


async def test_get_many_full_read_issues_a_single_query(monkeypatch, session_factory):
    monkeypatch.setattr(water_route_repository, "FULL_READ_THRESHOLD", 2)
    async with session_factory() as session:
        repo = WaterRouteRepository(session)
        await repo.save(A, B, RoutedLeg("ok", [A, B], 1.0))
        calls = []
        original = session.execute

        async def counting(*args, **kwargs):
            calls.append(1)
            return await original(*args, **kwargs)

        monkeypatch.setattr(session, "execute", counting)
        await repo.get_many([(A, B), (B, C), (A, C)])
    assert len(calls) == 1

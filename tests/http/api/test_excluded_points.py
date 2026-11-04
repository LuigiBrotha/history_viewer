import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.http.api.uboats import excluded_points
from app.http.api.uboats.excluded_points import ExcludedPointIn, RequestHandler
from app.http.api.uboats.status import RequestHandler as StatusHandler
from app.services.routing.types import RoutedLeg
from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import ExcludedRoutePoint, Patrol
from app.services.storage.patrol_repository import PatrolRepository

LOCAL = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
NETWORK = SimpleNamespace(client=SimpleNamespace(host="192.168.2.20"), headers={})


def fake_route_leg(start, end):
    return RoutedLeg(status="ok", path=[start, end], length_km=1.0)


@pytest.fixture
def routing(monkeypatch):
    async def loader():
        return fake_route_leg
    monkeypatch.setattr(excluded_points, "load_route_leg", loader)


async def make_db(tmp_path, n_points=3):
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
            external_id="p1", patrol_number=1, commander=None,
            departure_port=None, departure_date=None, arrival_port=None, arrival_date=None,
            days_at_sea=None, tonnage=None, detail_url="https://uboat.net/boats/patrols/p1.html",
        )
        points = [RoutePointData(i, 50.0 + i, -5.0 + i, None) for i in range(n_points)]
        await PatrolRepository(session).upsert_patrol(boat_id, summary, PatrolDetail(None, points))
    return engine, session_factory


async def get_route(session_factory):
    async with session_factory() as session:
        return await PatrolRepository(session).get_route("p1")


async def test_excluding_a_point_computes_the_new_leg(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    before = await get_route(sf)
    assert [leg.status for leg in before.legs] == ["not_computed", "not_computed"]

    result = await RequestHandler(sf).exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))

    assert [p.sequence for p in result.points] == [0, 2]
    assert [p.sequence for p in result.excluded_points] == [1]
    assert [leg.status for leg in result.legs] == ["ok"]
    assert result == await get_route(sf)
    await engine.dispose()


async def test_patrol_is_touched_only_when_routing_added_a_leg(tmp_path, routing, monkeypatch):
    touched = []
    real_touch = PatrolRepository.touch

    async def spy(self, external_id):
        touched.append(external_id)
        await real_touch(self, external_id)

    monkeypatch.setattr(PatrolRepository, "touch", spy)
    engine, sf = await make_db(tmp_path)
    handler = RequestHandler(sf)

    await handler.exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert touched == ["p1"]

    # Restoring needs A-B and B-C, which were never computed: another touch.
    await handler.restore(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert touched == ["p1", "p1"]

    # Restoring again changes nothing and computes nothing, so there is no extra touch.
    await handler.restore(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert touched == ["p1", "p1"]
    await engine.dispose()


async def test_exclusion_succeeds_when_routing_fails(tmp_path, monkeypatch):
    def broken(start, end):
        raise RuntimeError("no land data")

    async def loader():
        return broken
    monkeypatch.setattr(excluded_points, "load_route_leg", loader)
    engine, sf = await make_db(tmp_path)

    result = await RequestHandler(sf).exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))

    assert [p.sequence for p in result.points] == [0, 2]
    assert [leg.status for leg in result.legs] == ["not_computed"]
    await engine.dispose()


async def test_exclusion_succeeds_when_the_routing_engine_cannot_be_imported(tmp_path, monkeypatch):
    async def loader():
        return None
    monkeypatch.setattr(excluded_points, "load_route_leg", loader)
    engine, sf = await make_db(tmp_path)

    result = await RequestHandler(sf).exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))

    assert [leg.status for leg in result.legs] == ["not_computed"]
    await engine.dispose()


async def test_load_route_leg_returns_none_when_the_import_fails(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("app.routing_engine"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    assert await excluded_points.load_route_leg() is None


async def test_unknown_patrol_returns_404(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).exclude(request=LOCAL, external_id="nope", body=ExcludedPointIn(sequence=1))
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).restore(request=LOCAL, external_id="nope", body=ExcludedPointIn(sequence=1))
    assert exc.value.status_code == 404
    await engine.dispose()


async def test_unknown_sequence_returns_404(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=99))
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).restore(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=99))
    assert exc.value.status_code == 404
    await engine.dispose()


async def test_excluding_the_last_point_returns_409(tmp_path, routing):
    engine, sf = await make_db(tmp_path, n_points=1)
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=0))
    assert exc.value.status_code == 409
    await engine.dispose()


async def test_restoring_returns_the_point_to_the_route(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    handler = RequestHandler(sf)
    await handler.exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))

    result = await handler.restore(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))

    assert [p.sequence for p in result.points] == [0, 1, 2]
    assert result.excluded_points == []
    # Legs for the restored pairs are computed on restore.
    assert [leg.status for leg in result.legs] == ["ok", "ok"]
    await engine.dispose()


async def test_restoring_computes_missing_legs(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    handler = RequestHandler(sf)
    await handler.exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))
    result = await handler.restore(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert all(leg.status == "ok" for leg in result.legs)
    await engine.dispose()


def test_main_binds_to_loopback():
    source = (Path(__file__).resolve().parents[3] / "app" / "main.py").read_text()
    assert re.search(r'uvicorn\.run\([^)]*host="127\.0\.0\.1"', source)


async def count_exclusions(sf):
    async with sf() as session:
        return await session.scalar(select(func.count()).select_from(ExcludedRoutePoint))


async def test_excluding_from_a_network_client_returns_403_and_changes_nothing(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    before = await get_route(sf)
    async with sf() as session:
        stamp = await session.scalar(select(Patrol.updated_at).where(Patrol.external_id == "p1"))

    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).exclude(request=NETWORK, external_id="p1", body=ExcludedPointIn(sequence=1))

    assert exc.value.status_code == 403
    assert await count_exclusions(sf) == 0
    assert await get_route(sf) == before
    async with sf() as session:
        assert await session.scalar(select(Patrol.updated_at).where(Patrol.external_id == "p1")) == stamp
    await engine.dispose()


async def test_restoring_from_a_network_client_returns_403_and_changes_nothing(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    await RequestHandler(sf).exclude(request=LOCAL, external_id="p1", body=ExcludedPointIn(sequence=1))

    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).restore(request=NETWORK, external_id="p1", body=ExcludedPointIn(sequence=1))

    assert exc.value.status_code == 403
    assert await count_exclusions(sf) == 1
    await engine.dispose()


async def test_a_spoofed_forwarded_header_does_not_make_a_network_client_local(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    spoofed = SimpleNamespace(
        client=SimpleNamespace(host="192.168.2.20"),
        headers={"x-forwarded-for": "127.0.0.1", "forwarded": "for=127.0.0.1", "x-real-ip": "127.0.0.1"},
    )
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).exclude(request=spoofed, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert exc.value.status_code == 403
    assert (await StatusHandler(sf).handle_request(spoofed)).can_edit is False
    await engine.dispose()


async def test_a_missing_client_is_not_loopback(tmp_path, routing):
    engine, sf = await make_db(tmp_path)
    nobody = SimpleNamespace(client=None, headers={})
    with pytest.raises(HTTPException) as exc:
        await RequestHandler(sf).exclude(request=nobody, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert exc.value.status_code == 403
    await engine.dispose()


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "::ffff:127.0.0.1"])
async def test_loopback_clients_may_edit_including_ipv6(tmp_path, routing, host):
    engine, sf = await make_db(tmp_path)
    request = SimpleNamespace(client=SimpleNamespace(host=host), headers={})
    result = await RequestHandler(sf).exclude(request=request, external_id="p1", body=ExcludedPointIn(sequence=1))
    assert [p.sequence for p in result.points] == [0, 2]
    await engine.dispose()


async def test_status_reports_can_edit_only_for_a_loopback_client(tmp_path):
    engine, sf = await make_db(tmp_path)
    handler = StatusHandler(sf)
    assert (await handler.handle_request(LOCAL)).can_edit is True
    assert (await handler.handle_request(SimpleNamespace(client=SimpleNamespace(host="::1"), headers={}))).can_edit is True
    assert (await handler.handle_request(NETWORK)).can_edit is False
    assert (await handler.handle_request()).can_edit is False
    await engine.dispose()

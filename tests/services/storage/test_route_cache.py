import json

import pytest
from sqlalchemy import update

from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Patrol
from app.services.storage.patrol_repository import PatrolRepository
from app.services.storage.route_cache import RouteCache


@pytest.fixture
async def factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    yield create_session_factory(engine)
    await engine.dispose()


async def _store(factory, external_id, number, lat=1.0, slug="u99"):
    async with factory() as session:
        boats = BoatRepository(session)
        await boats.upsert_boat(BoatData(
            slug=slug, number=slug.upper(), type=None, builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))
        boat_id = await boats.get_id_by_slug(slug)
        await PatrolRepository(session).upsert_patrol(
            boat_id,
            PatrolSummary(
                external_id=external_id, patrol_number=number, commander=None, departure_port=None,
                departure_date=None, arrival_port=None, arrival_date=None, days_at_sea=None,
                tonnage=None, detail_url="https://uboat.net/x",
            ),
            PatrolDetail(description=None, route_points=[RoutePointData(0, lat, 2.0, None)]),
        )


async def _ids(cache, **page):
    return [patrol["external_id"] for patrol in json.loads(await cache.page(**page))]


async def test_page_returns_the_same_json_as_the_repository(factory):
    await _store(factory, "a", 1)

    routes = json.loads(await RouteCache(factory).page())

    assert routes[0]["external_id"] == "a"
    assert routes[0]["boat_slug"] == "u99"
    assert routes[0]["points"][0]["lat"] == 1.0
    assert routes[0]["legs"] == []


async def test_page_returns_a_slice_in_a_stable_order(factory):
    for number, external_id in enumerate("abc", start=1):
        await _store(factory, external_id, number)
    cache = RouteCache(factory)

    assert await _ids(cache, limit=2, offset=0) == ["a", "b"]
    assert await _ids(cache, limit=2, offset=2) == ["c"]
    assert await _ids(cache) == ["a", "b", "c"]


async def test_page_of_an_empty_database_is_an_empty_list(factory):
    assert json.loads(await RouteCache(factory).page()) == []


async def test_a_new_patrol_appears_in_its_sorted_place(factory):
    await _store(factory, "b", 2)
    cache = RouteCache(factory)
    await cache.page()

    await _store(factory, "a", 1)

    assert await _ids(cache) == ["a", "b"]


async def test_a_changed_patrol_is_refreshed(factory):
    await _store(factory, "a", 1, lat=1.0)
    cache = RouteCache(factory)
    await cache.page()

    await _store(factory, "a", 1, lat=5.0)

    assert json.loads(await cache.page())[0]["points"][0]["lat"] == 5.0


async def test_an_unchanged_database_is_not_read_again(factory, monkeypatch):
    await _store(factory, "a", 1)
    cache = RouteCache(factory)
    await cache.page()
    calls = []
    real = PatrolRepository.list_routes

    async def counting(self, *args, **kwargs):
        calls.append(kwargs)
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(PatrolRepository, "list_routes", counting)

    await cache.page()

    assert calls == []


async def test_only_changed_patrols_are_read_on_a_refresh(factory, monkeypatch):
    await _store(factory, "a", 1)
    cache = RouteCache(factory)
    await cache.page()
    await _store(factory, "b", 2)
    calls = []
    real = PatrolRepository.list_routes

    async def counting(self, *args, **kwargs):
        calls.append(kwargs.get("since"))
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(PatrolRepository, "list_routes", counting)

    await cache.page()

    assert len(calls) == 1 and calls[0] is not None


async def test_patrols_without_a_timestamp_are_served(factory):
    await _store(factory, "a", 1)
    async with factory() as session:
        await session.execute(update(Patrol).values(updated_at=None, crawled_at=None))
        await session.commit()

    assert await _ids(RouteCache(factory)) == ["a"]


async def test_two_requests_at_once_load_only_once(factory, monkeypatch):
    import asyncio

    await _store(factory, "a", 1)
    calls = []
    real = PatrolRepository.list_routes

    async def counting(self, *args, **kwargs):
        calls.append(1)
        return await real(self, *args, **kwargs)

    monkeypatch.setattr(PatrolRepository, "list_routes", counting)
    cache = RouteCache(factory)

    await asyncio.gather(cache.page(), cache.page())

    assert len(calls) == 1

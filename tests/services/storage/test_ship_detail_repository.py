from contextlib import asynccontextmanager

from app.services.scraping.uboat_net.types import ShipDetails
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.ship_detail_repository import ShipDetailRepository


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    try:
        async with create_session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()


async def test_get_returns_none_for_an_unknown_ship(tmp_path):
    async with _session(tmp_path) as session:
        assert await ShipDetailRepository(session).get("408") is None


async def test_save_stores_details_and_a_second_save_replaces_them(tmp_path):
    async with _session(tmp_path) as session:
        repo = ShipDetailRepository(session)
        await repo.save("408", ShipDetails(owner="Old", cargo="timber", notes="At sea"))
        await repo.save("408", ShipDetails(owner="Canada Steamship Lines Ltd, Montreal"))

        details = await repo.get("408")

    assert details == ShipDetails(owner="Canada Steamship Lines Ltd, Montreal")

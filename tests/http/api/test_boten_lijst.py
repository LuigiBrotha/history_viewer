from app.http.api.uboats.boten_lijst import RequestHandler
from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def test_handle_request_returns_boat_summaries(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(BoatData(
            slug="u99", number="U-99", type="VIIB", builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))

    result = await RequestHandler(session_factory).handle_request()

    assert len(result) == 1
    assert result[0].slug == "u99"

    await engine.dispose()

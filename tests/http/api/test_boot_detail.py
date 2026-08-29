import pytest
from fastapi import HTTPException

from app.http.api.uboats.boot_detail import RequestHandler
from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def test_handle_request_returns_boat_detail(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(BoatData(
            slug="u99", number="U-99", type="VIIB", builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))

    result = await RequestHandler(session_factory).handle_request("u99")

    assert result.slug == "u99"
    assert result.type == "VIIB"

    await engine.dispose()


async def test_handle_request_raises_404_for_unknown_slug(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    with pytest.raises(HTTPException) as exc_info:
        await RequestHandler(session_factory).handle_request("unknown")

    assert exc_info.value.status_code == 404

    await engine.dispose()

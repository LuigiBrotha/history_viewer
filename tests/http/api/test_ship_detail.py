from datetime import date

import pytest
from fastapi import HTTPException

from app.http.api.uboats.ship_detail import RequestHandler
from app.services.scraping.uboat_net.types import ShipDetails, ShipHitRef
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.ship_detail_repository import ShipDetailRepository
from app.services.storage.ship_hit_repository import ShipHitRepository


def _ref(ship_id, slug, day):
    return ShipHitRef(
        ship_id, slug, f"Ship {ship_id}", day, 2053, "ca", "HX-52", "sunk",
        f"https://uboat.net/allies/merchants/ship/{ship_id}.html",
    )


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return engine, create_session_factory(engine)


async def test_returns_the_details_and_every_hit_of_the_ship(tmp_path):
    engine, session_factory = await _session_factory(tmp_path)
    async with session_factory() as session:
        await ShipHitRepository(session).upsert_refs(
            [_ref("408", "u99", date(1940, 7, 5)), _ref("408", "u100", date(1940, 7, 8)), _ref("9", "u99", date(1940, 7, 9))]
        )
        await ShipDetailRepository(session).save("408", ShipDetails(owner="Canada Steamship Lines Ltd, Montreal"))

    result = await RequestHandler(session_factory).handle_request("408")

    assert result.ship_external_id == "408"
    assert result.details.owner == "Canada Steamship Lines Ltd, Montreal"
    assert [(h.boat_slug, h.date) for h in result.hits] == [("u99", date(1940, 7, 5)), ("u100", date(1940, 7, 8))]
    await engine.dispose()


async def test_details_are_null_until_the_page_is_fetched(tmp_path):
    engine, session_factory = await _session_factory(tmp_path)
    async with session_factory() as session:
        await ShipHitRepository(session).upsert_refs([_ref("408", "u99", date(1940, 7, 5))])

    result = await RequestHandler(session_factory).handle_request("408")

    assert result.details is None
    assert len(result.hits) == 1
    await engine.dispose()


async def test_unknown_ship_is_a_404(tmp_path):
    engine, session_factory = await _session_factory(tmp_path)

    with pytest.raises(HTTPException) as error:
        await RequestHandler(session_factory).handle_request("nope")

    assert error.value.status_code == 404
    await engine.dispose()

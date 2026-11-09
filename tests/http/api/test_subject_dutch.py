from datetime import date

import pytest

from app.http.api.uboats.boot_detail import RequestHandler as BoatHandler
from app.http.api.uboats.ship_detail import RequestHandler as ShipHandler
from app.services.scraping.uboat_net.types import BoatData, ShipDetails, ShipHitRef
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.ship_detail_repository import ShipDetailRepository
from app.services.storage.ship_hit_repository import ShipHitRepository
from app.services.wiki.article_service import ArticleService


class FakeModels:
    def __init__(self, can=True):
        self.can = can
        self.calls = []

    def can_reach_dutch(self, lang):
        return self.can

    def to_dutch(self, lang, texts):
        self.calls.append((lang, list(texts)))
        return [f"NL[{t}]" for t in texts]


@pytest.fixture
async def factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(BoatData(
            slug="u99", number="U-99", type="VIIB", builder="Kiel",
            laid_down=None, launched=None, commissioned=None, fate="Scuttled",
        ))
        await ShipHitRepository(session).upsert_refs([ShipHitRef(
            "408", "u99", "Magog", date(1940, 7, 5), 2053, "ca", "HX-52", "sunk",
            "https://uboat.net/allies/merchants/ship/408.html",
        )])
        await ShipDetailRepository(session).save("408", ShipDetails(owner="Acme", notes="At noon", cargo="Timber"))
    yield session_factory
    await engine.dispose()


async def test_a_boats_running_text_comes_in_dutch_and_is_made_once(factory):
    models = FakeModels()
    handler = BoatHandler(factory, ArticleService(factory, models))
    first = await handler.handle_request("u99", versie="nl")
    assert first.fate == "NL[Scuttled]" and first.translated and first.builder == "Kiel"
    second = await handler.handle_request("u99", versie="nl")
    assert second.fate == "NL[Scuttled]"
    assert len(models.calls) == 1


async def test_the_original_of_a_boat_translates_nothing(factory):
    models = FakeModels()
    result = await BoatHandler(factory, ArticleService(factory, models)).handle_request("u99")
    assert result.fate == "Scuttled" and not result.translated and models.calls == []


async def test_only_a_ships_running_text_is_translated(factory):
    handler = ShipHandler(factory, ArticleService(factory, FakeModels()))
    result = await handler.handle_request("408", versie="nl")
    assert result.translated
    assert result.details.notes == "NL[At noon]" and result.details.cargo == "NL[Timber]"
    assert result.details.owner == "Acme"


async def test_without_a_model_the_original_comes_back_and_says_so(factory):
    handler = ShipHandler(factory, ArticleService(factory, FakeModels(can=False)))
    result = await handler.handle_request("408", versie="nl")
    assert not result.translated and result.details.notes == "At noon"

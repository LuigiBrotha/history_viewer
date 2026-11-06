import pytest
from fastapi import HTTPException

from app.http.api.places.search import RequestHandler
from app.services.places.photon import PhotonError
from app.services.storage.database import create_engine, create_session_factory, init_models

RESULT = [{"name": "Narvik", "sub": "Nordland, Norge", "lat": 68.0, "lng": 17.0, "bbox": None}]


class FakeClient:
    def __init__(self, results=RESULT, error=None):
        self.results = results
        self.error = error
        self.calls = []

    async def search(self, query):
        self.calls.append(query)
        if self.error:
            raise self.error
        return self.results


async def make_handler(tmp_path, client):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return engine, RequestHandler(create_session_factory(engine), client)


async def test_cache_miss_then_hit(tmp_path):
    client = FakeClient()
    engine, handler = await make_handler(tmp_path, client)
    first = await handler.search_places("  Narvik ")
    second = await handler.search_places("narvik")
    assert len(client.calls) == 1
    assert [r.model_dump() for r in first] == RESULT == [r.model_dump() for r in second]
    await engine.dispose()


async def test_empty_result_is_cached(tmp_path):
    client = FakeClient(results=[])
    engine, handler = await make_handler(tmp_path, client)
    assert await handler.search_places("Nowhere") == []
    assert await handler.search_places("nowhere") == []
    assert len(client.calls) == 1
    await engine.dispose()


@pytest.mark.parametrize("q", ["   ", "x" * 201])
async def test_blank_and_long_query_422(tmp_path, q):
    client = FakeClient()
    engine, handler = await make_handler(tmp_path, client)
    with pytest.raises(HTTPException) as info:
        await handler.search_places(q)
    assert info.value.status_code == 422
    assert client.calls == []
    await engine.dispose()


async def test_photon_failure_503_not_cached(tmp_path):
    client = FakeClient(error=PhotonError("boom"))
    engine, handler = await make_handler(tmp_path, client)
    with pytest.raises(HTTPException) as info:
        await handler.search_places("Narvik")
    assert info.value.status_code == 503
    assert info.value.detail == "Plaatsen zoeken mislukt."
    with pytest.raises(HTTPException):
        await handler.search_places("Narvik")
    assert len(client.calls) == 2
    await engine.dispose()

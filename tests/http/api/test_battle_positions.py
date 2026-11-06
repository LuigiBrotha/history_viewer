from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.http.api.battles import positions
from app.http.api.battles.positions import BattlePositionIn, RequestHandler
from app.services.storage.database import create_engine, create_session_factory, init_models

TITLES = ["Battle of the Atlantic", "Battle of the Bulge (1944–45)", 'Operation "Weserübung"']


def fake_request(peer="127.0.0.1", **headers):
    headers = {"host": "localhost:8000", **headers}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


LOCAL = fake_request()
NETWORK = fake_request("192.168.2.20", host="192.168.2.10:8001")


@pytest.fixture(autouse=True)
def known(monkeypatch):
    monkeypatch.setattr(positions, "known_battle_titles", lambda: frozenset(TITLES))


async def make_handler(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return engine, RequestHandler(create_session_factory(engine))


def body(lat=10.0, lng=20.0):
    return BattlePositionIn(lat=lat, lng=lng)


async def test_get_returns_stored_rows(tmp_path):
    engine, handler = await make_handler(tmp_path)
    await handler.put_position(LOCAL, TITLES[0], body())
    result = await handler.list_positions()
    assert [(r.title, r.lat, r.lng) for r in result] == [(TITLES[0], 10.0, 20.0)]
    await engine.dispose()


async def test_put_stores_and_returns_the_row(tmp_path):
    engine, handler = await make_handler(tmp_path)
    result = await handler.put_position(LOCAL, TITLES[0], body(1.0, 2.0))
    assert (result.title, result.lat, result.lng) == (TITLES[0], 1.0, 2.0)
    await engine.dispose()


@pytest.mark.parametrize("lat,lng", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_out_of_range_coordinates_are_rejected(lat, lng):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        BattlePositionIn(lat=lat, lng=lng)


async def test_put_for_an_unknown_title_is_404(tmp_path):
    engine, handler = await make_handler(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await handler.put_position(LOCAL, "Nope", body())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Onbekende veldslag."
    assert await handler.list_positions() == []
    await engine.dispose()


async def test_put_and_delete_from_a_network_client_are_403(tmp_path):
    engine, handler = await make_handler(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await handler.put_position(NETWORK, TITLES[0], body())
    assert exc.value.status_code == 403
    await handler.put_position(LOCAL, TITLES[0], body())
    with pytest.raises(HTTPException) as exc:
        await handler.delete_position(NETWORK, TITLES[0])
    assert exc.value.status_code == 403
    assert len(await handler.list_positions()) == 1
    await engine.dispose()


async def test_delete_returns_204_and_removes_the_row(tmp_path):
    engine, handler = await make_handler(tmp_path)
    await handler.put_position(LOCAL, TITLES[0], body())
    response = await handler.delete_position(LOCAL, TITLES[0])
    assert response.status_code == 204
    assert await handler.list_positions() == []
    await engine.dispose()


@pytest.mark.parametrize("title", TITLES[1:])
async def test_titles_with_special_characters_round_trip(tmp_path, title):
    engine, handler = await make_handler(tmp_path)
    await handler.put_position(LOCAL, title, body())
    assert [r.title for r in await handler.list_positions()] == [title]
    await handler.delete_position(LOCAL, title)
    assert await handler.list_positions() == []
    await engine.dispose()

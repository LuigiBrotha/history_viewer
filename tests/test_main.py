import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests
from sqlalchemy import update

from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory
from app.services.storage.models import Patrol
from app.services.storage.patrol_repository import PatrolRepository

REPO_ROOT = Path(__file__).resolve().parent.parent


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def reload_server(tmp_path):
    port = _free_port()
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path}/test.db",
        "BASE_URL": f"http://127.0.0.1:{port}",
        "ROOT_PATH": "",
        "BASE_DIR": "app",
        "HTTP_DIR": "app/http",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                requests.get(f"{base_url}/api/uboats/boten", timeout=1)
                break
            except requests.ConnectionError:
                if time.monotonic() > deadline:
                    pytest.fail("server started with --reload never accepted connections")
                time.sleep(0.2)
        yield base_url
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


def test_reload_server_creates_tables_on_a_fresh_database(reload_server):
    response = requests.get(f"{reload_server}/api/uboats/boten", timeout=5)

    assert response.status_code == 200
    assert response.json() == []


def test_reload_server_serves_the_map_at_the_root(reload_server):
    response = requests.get(f"{reload_server}/", timeout=5)

    assert response.status_code == 200
    assert '<div id="map">' in response.text


def test_reload_server_serves_frontend_assets(reload_server):
    response = requests.get(f"{reload_server}/js/main.js", timeout=5)

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_reload_server_serves_the_status_map_without_a_redirect(reload_server):
    response = requests.get(f"{reload_server}/status", timeout=5, allow_redirects=False)

    assert response.status_code == 200
    assert '<div id="status-map">' in response.text


async def _seed_two_patrols(db_path):
    from datetime import datetime, timezone

    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        boat_repo = BoatRepository(session)
        await boat_repo.upsert_boat(BoatData(
            slug="u99", number="U-99", type=None, builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))
        boat_id = await boat_repo.get_id_by_slug("u99")
        for number, external_id, hour in [(1, "old", 9), (2, "new", 11)]:
            summary = PatrolSummary(
                external_id=external_id, patrol_number=number, commander=None,
                departure_port=None, departure_date=None, arrival_port=None, arrival_date=None,
                days_at_sea=None, tonnage=None, detail_url=f"https://uboat.net/boats/patrols/{external_id}.html",
            )
            await PatrolRepository(session).upsert_patrol(boat_id, summary, PatrolDetail(None, []))
            stamp = datetime(2026, 11, 4, hour, 0, tzinfo=timezone.utc)
            await session.execute(update(Patrol).where(Patrol.external_id == external_id).values(updated_at=stamp))
        await session.commit()
    await engine.dispose()


def test_status_revision_fed_back_as_since_returns_that_patrol(reload_server, tmp_path):
    asyncio.run(_seed_two_patrols(tmp_path / "test.db"))

    status = requests.get(f"{reload_server}/api/uboats/status", timeout=5).json()
    response = requests.get(f"{reload_server}/api/uboats/routes", params={"since": status["revision"]}, timeout=5)

    assert response.status_code == 200
    assert [route["external_id"] for route in response.json()] == ["new"]


async def _seed_long_patrol(db_path):
    from app.services.scraping.uboat_net.types import RoutePointData

    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        boat_repo = BoatRepository(session)
        await boat_repo.upsert_boat(BoatData(
            slug="u99", number="U-99", type=None, builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))
        boat_id = await boat_repo.get_id_by_slug("u99")
        summary = PatrolSummary(
            external_id="long", patrol_number=1, commander=None,
            departure_port=None, departure_date=None, arrival_port=None, arrival_date=None,
            days_at_sea=None, tonnage=None, detail_url="https://uboat.net/boats/patrols/long.html",
        )
        points = [RoutePointData(i, 50.0 + i * 0.1, -5.0 + i * 0.1, None) for i in range(60)]
        await PatrolRepository(session).upsert_patrol(boat_id, summary, PatrolDetail(None, points))
        await session.commit()
    await engine.dispose()


def test_routes_are_gzip_encoded_when_asked_for(reload_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))

    response = requests.get(
        f"{reload_server}/api/uboats/routes", headers={"Accept-Encoding": "gzip"}, timeout=5,
    )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert len(response.json()[0]["points"]) == 60

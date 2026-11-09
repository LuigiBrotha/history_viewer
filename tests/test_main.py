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


def test_reload_server_serves_frontend_assets(reload_server):
    response = requests.get(f"{reload_server}/js/main.js", timeout=5)

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/", "/dag-tot-dag", "/heatmap", "/js/main.js", "/css/style.css"])
def test_pages_and_assets_must_be_revalidated_after_an_update(reload_server, path):
    response = requests.get(f"{reload_server}{path}", timeout=5)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_reload_server_serves_the_tonnage_chart_without_a_redirect(reload_server):
    response = requests.get(f"{reload_server}/grafiek", timeout=5, allow_redirects=False)
    assert response.status_code == 200
    assert "js/tonnage.js" in response.text


def test_reload_server_serves_the_heatmap_without_a_redirect(reload_server):
    response = requests.get(f"{reload_server}/heatmap", timeout=5, allow_redirects=False)
    assert response.status_code == 200
    assert '<div id="status-map">' in response.text
    assert "js/heatmap.js" in response.text


def test_the_root_is_the_map_of_all_routes(reload_server):
    response = requests.get(f"{reload_server}/", timeout=5, allow_redirects=False)

    assert response.status_code == 200
    assert '<div id="status-map">' in response.text
    assert "js/status.js" in response.text


def test_the_timeline_is_at_dag_tot_dag(reload_server):
    response = requests.get(f"{reload_server}/dag-tot-dag", timeout=5, allow_redirects=False)

    assert response.status_code == 200
    assert "js/main.js" in response.text


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("/status", "./"),
        ("/status?van=1942-01-01&kaart=1,2,3", "./?van=1942-01-01&kaart=1,2,3"),
        ("/?datum=1942-05-15&boot=u172", "dag-tot-dag?datum=1942-05-15&boot=u172"),
    ],
)
def test_old_addresses_lead_to_the_right_page_with_their_view(reload_server, path, location):
    response = requests.get(f"{reload_server}{path}", timeout=5, allow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == location


def test_a_view_without_a_date_stays_on_the_root(reload_server):
    response = requests.get(f"{reload_server}/?van=1942-01-01", timeout=5, allow_redirects=False)

    assert response.status_code == 200
    assert "js/status.js" in response.text


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


def test_exclusion_routes_parse_a_json_body_over_real_http(reload_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))
    url = f"{reload_server}/api/uboats/routes/long/excluded-points"

    assert requests.get(f"{reload_server}/api/uboats/status", timeout=5).json()["can_edit"] is True
    assert requests.post(f"{reload_server}/api/uboats/routes/nope/excluded-points",
                         json={"sequence": 1}, timeout=5).status_code == 404
    assert requests.post(url, json={"sequence": "x"}, timeout=5).status_code == 422
    assert requests.delete(url, json={"sequence": 999}, timeout=5).status_code == 404


def _lan_address():
    """This machine's non-loopback IPv4 address, or None when it has no network."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("192.0.2.1", 9))  # TEST-NET-1: no packet is sent
            address = sock.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith("127.") else address


@pytest.fixture
def lan_server(tmp_path):
    """A server on all interfaces that trusts forwarding headers from anyone, the worst case."""
    port = _free_port()
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path}/test.db",
        "BASE_URL": f"http://127.0.0.1:{port}",
        "ROOT_PATH": "",
        "BASE_DIR": "app",
        "HTTP_DIR": "app/http",
        "FORWARDED_ALLOW_IPS": "*",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
        cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                requests.get(f"http://127.0.0.1:{port}/api/uboats/boten", timeout=1)
                break
            except requests.ConnectionError:
                if time.monotonic() > deadline:
                    pytest.fail("server never accepted connections")
                time.sleep(0.2)
        yield port
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


def _excluded_url(port, host="127.0.0.1"):
    return f"http://{host}:{port}/api/uboats/routes/long/excluded-points"


def test_real_socket_loopback_can_exclude_and_restore(lan_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))
    url = _excluded_url(lan_server)

    excluded = requests.post(url, json={"sequence": 5}, timeout=120)
    assert excluded.status_code == 200
    assert [p["sequence"] for p in excluded.json()["excluded_points"]] == [5]
    assert len(excluded.json()["points"]) == 59

    restored = requests.delete(url, json={"sequence": 5}, timeout=120)
    assert restored.status_code == 200
    assert restored.json()["excluded_points"] == []
    assert len(restored.json()["points"]) == 60


def test_real_socket_foreign_host_header_is_refused(lan_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))

    response = requests.post(_excluded_url(lan_server), json={"sequence": 5}, headers={"Host": "evil.example"}, timeout=10)

    assert response.status_code == 403
    status = requests.get(f"http://127.0.0.1:{lan_server}/api/uboats/status", headers={"Host": "evil.example"}, timeout=10)
    assert status.json()["can_edit"] is False


def test_real_socket_foreign_origin_is_refused(lan_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))

    response = requests.post(
        _excluded_url(lan_server), json={"sequence": 5}, headers={"Origin": "http://evil.example"}, timeout=10,
    )

    assert response.status_code == 403


def test_real_socket_text_plain_body_is_not_parsed(lan_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))

    response = requests.post(
        _excluded_url(lan_server), data='{"sequence": 5}', headers={"Content-Type": "text/plain"}, timeout=10,
    )

    assert response.status_code == 422


def test_real_socket_forwarding_header_from_loopback_is_refused(lan_server, tmp_path):
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))

    response = requests.post(
        _excluded_url(lan_server), json={"sequence": 5}, headers={"X-Forwarded-For": "127.0.0.1"}, timeout=10,
    )

    assert response.status_code == 403


def test_real_socket_network_client_is_refused_even_with_spoofed_forwarding(lan_server, tmp_path):
    address = _lan_address()
    if address is None:
        pytest.skip("this machine has no non-loopback IPv4 address to connect through")
    asyncio.run(_seed_long_patrol(tmp_path / "test.db"))
    url = _excluded_url(lan_server, address)

    plain = requests.post(url, json={"sequence": 5}, timeout=10)
    spoofed = requests.post(url, json={"sequence": 5}, headers={"X-Forwarded-For": "127.0.0.1"}, timeout=10)
    invalid = requests.post(url, data="x", headers={"Content-Type": "text/plain"}, timeout=10)
    status = requests.get(f"http://{address}:{lan_server}/api/uboats/status", headers={"X-Forwarded-For": "127.0.0.1"}, timeout=10)

    assert plain.status_code == 403
    assert spoofed.status_code == 403
    assert invalid.status_code == 403
    assert status.json()["can_edit"] is False
    assert requests.get(f"http://{address}:{lan_server}/api/uboats/routes", timeout=10).json()[0]["excluded_points"] == []

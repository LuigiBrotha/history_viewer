import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

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

import asyncio

import pytest
from fastapi import FastAPI, HTTPException

from app.http.api.battles.image import RequestHandler
from app.main import RevalidateMiddleware
from app.services.wiki.image_cache import ImageCache, thumbnail_urls


class CountingFetch:
    def __init__(self, data=b"png"):
        self.data = data
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return self.data


@pytest.fixture
def fetch():
    return CountingFetch()


@pytest.fixture
def handler(tmp_path, fetch):
    return RequestHandler(ImageCache(fetch, tmp_path))


@pytest.mark.parametrize("name", ["../../etc/passwd", "x.html", "a/../b.jpg", "x" * 300 + ".jpg"])
async def test_unsafe_or_non_image_names_are_404_without_a_fetch(handler, fetch, name):
    with pytest.raises(HTTPException) as caught:
        await handler.handle_request(name)
    assert caught.value.status_code == 404
    assert fetch.urls == []


async def test_image_is_served_immutable_from_the_cache(handler, fetch, tmp_path):
    response = await handler.handle_request("Map.JPG", 400)
    assert response.headers["cache-control"] == "max-age=31536000, immutable"
    assert response.path.read_bytes() == b"png"
    assert fetch.urls == [thumbnail_urls("Map.JPG", 500)[0]]


async def test_missing_image_is_404(tmp_path):
    handler = RequestHandler(ImageCache(lambda url: None, tmp_path))
    with pytest.raises(HTTPException) as caught:
        await handler.handle_request("Gone.jpg")
    assert caught.value.status_code == 404


async def _cache_control_headers(app, path):
    messages = []
    requested = []

    async def receive():
        # The client stays connected: a later call waits, as a real server's would.
        if requested:
            await asyncio.Event().wait()
        requested.append(1)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"",
        "headers": [], "scheme": "http", "server": ("test", 80), "client": ("test", 1),
        "http_version": "1.1", "root_path": "",
    }
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    return [value.decode() for name, value in start["headers"] if name == b"cache-control"]


async def test_revalidate_middleware_keeps_the_route_cache_control(handler):
    app = FastAPI()
    app.add_api_route("/img/{file_name}", handler.handle_request)
    app.add_api_route("/plain", lambda: {"ok": 1})
    wrapped = RevalidateMiddleware(app)

    assert await _cache_control_headers(wrapped, "/img/Map.jpg") == ["max-age=31536000, immutable"]
    assert await _cache_control_headers(wrapped, "/plain") == ["no-cache"]

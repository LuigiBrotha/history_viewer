import hashlib
from urllib.parse import quote

import pytest

from app.services.wiki import image_cache
from app.services.wiki.image_cache import ImageCache, image_url_for, snap_width, thumbnail_urls


def _md5(name):
    return hashlib.md5(name.encode()).hexdigest()


class FakeFetch:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        response = self.responses.get(url)
        if isinstance(response, Exception):
            raise response
        return response


def test_commons_url_comes_first_then_en():
    md5 = _md5("Bundesarchiv_Bild_101II.jpg")
    urls = thumbnail_urls("Bundesarchiv Bild 101II.jpg", 330)
    assert urls[0] == (
        f"https://upload.wikimedia.org/wikipedia/commons/thumb/{md5[0]}/{md5[:2]}/"
        "Bundesarchiv_Bild_101II.jpg/330px-Bundesarchiv_Bild_101II.jpg"
    )
    assert urls[1].startswith("https://upload.wikimedia.org/wikipedia/en/thumb/")


def test_svg_thumbnail_gets_a_png_suffix():
    assert thumbnail_urls("Flag.svg", 500)[0].endswith("/500px-Flag.svg.png")


def test_lower_case_first_letter_and_spaces_are_normalised():
    name = "Western_Approaches.PNG"
    md5 = _md5(name)
    assert f"/{md5[0]}/{md5[:2]}/{name}/" in thumbnail_urls("western Approaches.PNG", 330)[0]
    assert image_url_for("western Approaches.PNG", 330) == "/api/battles/images/Western_Approaches.PNG?width=330"


def test_image_url_quotes_the_name_and_snaps_the_width():
    assert image_url_for("HMS Achilles (70).jpg", 400) == (
        f"/api/battles/images/{quote('HMS_Achilles_(70).jpg')}?width=500"
    )


@pytest.mark.parametrize("width,expected", [(200, 330), (330, 330), (400, 500), (960, 960), (5000, 960)])
def test_width_snaps_up_and_caps(width, expected):
    assert snap_width(width) == expected


async def test_first_get_fetches_and_writes_second_reads_disk(tmp_path):
    url = thumbnail_urls("Map.jpg", 330)[0]
    fetch = FakeFetch({url: b"jpegdata"})
    cache = ImageCache(fetch, tmp_path)
    path = await cache.get("map.jpg", 330)
    assert path == tmp_path / "330" / _md5("Map.jpg")[:2] / "Map.jpg"
    assert path.read_bytes() == b"jpegdata"
    assert await cache.get("Map.jpg", 330) == path
    assert fetch.urls == [url]
    assert [p.name for p in path.parent.iterdir()] == ["Map.jpg"]


async def test_commons_404_falls_back_to_en(tmp_path):
    commons, en = thumbnail_urls("Map.jpg", 330)
    fetch = FakeFetch({en: b"endata"})
    path = await ImageCache(fetch, tmp_path).get("Map.jpg", 330)
    assert fetch.urls == [commons, en]
    assert path.read_bytes() == b"endata"


@pytest.mark.parametrize("failure", [None, TimeoutError("slow")])
async def test_failure_is_remembered_for_an_hour_and_writes_nothing(tmp_path, monkeypatch, failure):
    fetch = FakeFetch({url: failure for url in thumbnail_urls("Gone.jpg", 330)})
    cache = ImageCache(fetch, tmp_path)
    assert await cache.get("Gone.jpg", 330) is None
    assert len(fetch.urls) == 2
    assert await cache.get("Gone.jpg", 330) is None
    assert len(fetch.urls) == 2
    assert list(tmp_path.rglob("*")) == []

    now = image_cache.time.monotonic()
    monkeypatch.setattr(image_cache.time, "monotonic", lambda: now + 3601)
    assert await cache.get("Gone.jpg", 330) is None
    assert len(fetch.urls) == 4


@pytest.mark.parametrize("name", ["../../etc/passwd", "x.html", "a/b.jpg", "..\\b.jpg"])
async def test_unsafe_names_are_not_fetched(tmp_path, name):
    fetch = FakeFetch({})
    assert await ImageCache(fetch, tmp_path).get(name, 330) is None
    assert fetch.urls == []

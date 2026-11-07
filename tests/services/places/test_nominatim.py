import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from app.services.places import nominatim
from app.services.places.nominatim import NominatimClient, PlaceSearchError, parse_nominatim
from app.services.scraping.uboat_net.http_client import build_user_agent

NARVIK = [
    {"place_id": 1, "lat": "68.4383796", "lon": "17.4271978", "name": "Narvik",
     "display_name": "Narvik, Nordland, Norge", "boundingbox": ["68.2783796", "68.5983796", "17.2671978", "17.5871978"]},
    {"place_id": 2, "lat": "68.2898873", "lon": "17.0865077", "name": "Narvik",
     "display_name": "Narvik, Nordland, Norge"},
]


def place(name="X", lat="2.0", lon="1.0", **extra):
    found = {"lat": lat, "lon": lon, "name": name, "display_name": f"{name}, Land", **extra}
    if name is None:
        del found["name"]
    return found


def test_parse_maps_a_place():
    first, second = parse_nominatim(NARVIK)
    assert (first["name"], first["sub"]) == ("Narvik", "Nordland, Norge")
    assert (first["lat"], first["lng"]) == (68.4383796, 17.4271978)
    assert first["bbox"] == [68.2783796, 68.5983796, 17.2671978, 17.5871978]
    assert second["bbox"] is None


def test_parse_takes_the_first_part_of_the_display_name_without_a_name():
    result = parse_nominatim([place(None, display_name="Kanaal, Zeeland, Nederland")])
    assert (result[0]["name"], result[0]["sub"]) == ("Kanaal", "Zeeland, Nederland")


def test_parse_skips_unusable_points_and_keeps_five():
    payload = [place("Nan", lat="nan"), place("Text", lat="a"), place("High", lat="90.5"),
               place("Wide", lon="180.5"), place("Missing", lat=None), place("Ok", lat="-90", lon="180")]
    assert [r["name"] for r in parse_nominatim(payload)] == ["Ok"]
    assert len(parse_nominatim([place(f"P{i}") for i in range(8)])) == 5
    assert parse_nominatim({}) == []
    assert parse_nominatim([place("Bad box", boundingbox=["x", "1", "2", "3"])])[0]["bbox"] is None


class Fakes:
    def __init__(self):
        self.now = 100.0
        self.starts = []
        self.urls = []
        self.headers = None

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds

    async def fetch(self, url, headers):
        self.starts.append(self.now)
        self.urls.append(url)
        self.headers = headers
        return 200, json.dumps(NARVIK)


async def test_client_spaces_requests_one_second():
    fakes = Fakes()
    client = NominatimClient("me@example.org", fetch=fakes.fetch, clock=fakes.clock, sleep=fakes.sleep)
    await asyncio.gather(client.search("a"), client.search("b"))
    assert fakes.starts[1] - fakes.starts[0] >= 1.0


async def test_client_asks_nominatim_in_dutch_with_its_user_agent():
    fakes = Fakes()
    client = NominatimClient("me@example.org", fetch=fakes.fetch, clock=fakes.clock, sleep=fakes.sleep)
    result = await client.search("Narvik")
    url = urlparse(fakes.urls[0])
    assert (url.netloc, url.path) == ("nominatim.openstreetmap.org", "/search")
    assert parse_qs(url.query) == {"q": ["Narvik"], "format": ["jsonv2"], "limit": ["5"], "accept-language": ["nl,en"]}
    assert fakes.headers["User-Agent"] == build_user_agent("me@example.org")
    assert len(result) == 2


def make_failing(status, body):
    async def fetch(url, headers):
        return status, body
    return NominatimClient("", fetch=fetch)


async def test_client_raises_on_non_200_and_bad_json():
    with pytest.raises(PlaceSearchError):
        await make_failing(500, "").search("a")
    with pytest.raises(PlaceSearchError):
        await make_failing(200, "not json").search("a")


async def test_default_fetch_maps_request_exception(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.Timeout("slow")
    monkeypatch.setattr(nominatim.requests, "get", boom)
    with pytest.raises(PlaceSearchError):
        await nominatim._default_fetch("http://x", {})

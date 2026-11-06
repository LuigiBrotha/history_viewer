import asyncio
import json

from app.services.places.photon import PhotonClient, parse_photon
from app.services.scraping.uboat_net.http_client import build_user_agent

NARVIK = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {
        "osm_type": "N", "osm_id": 20981180, "osm_key": "place", "osm_value": "town", "type": "city",
        "name": "Narvik", "county": "Nordland", "country": "Norge", "postcode": "8517", "countrycode": "NO"},
     "geometry": {"type": "Point", "coordinates": [17.4271978, 68.4383796]}},
    {"type": "Feature", "properties": {
        "osm_type": "R", "osm_id": 10143373, "osm_key": "place", "osm_value": "municipality", "type": "city",
        "name": "Narvik", "county": "Nordland", "country": "Norge", "countrycode": "NO",
        "extra": {"admin_level": "7"}, "extent": [15.9014286, 68.6084547, 18.1513549, 67.9693704]},
     "geometry": {"type": "Point", "coordinates": [17.0865077, 68.2898873]}},
]}


def feature(name="X", coordinates=(1.0, 2.0), **props):
    properties = {"name": name, **props}
    if name is None:
        del properties["name"]
    return {"type": "Feature", "properties": properties, "geometry": {"type": "Point", "coordinates": list(coordinates)}}


def test_parse_maps_feature():
    result = parse_photon(NARVIK)[1]
    assert result["name"] == "Narvik"
    assert result["sub"] == "Nordland, Norge"
    assert result["lat"] == 68.2898873
    assert result["lng"] == 17.0865077
    assert result["bbox"] == [67.9693704, 68.6084547, 15.9014286, 18.1513549]


def test_parse_skips_nameless_and_tolerates_missing_extent():
    payload = {"features": [
        feature(None),
        feature("Ok", city="A", state="B"),
        feature("BadCoords", coordinates=(1.0,)),
        {"properties": {"name": "NoGeometry"}},
        feature("Strings", coordinates=("a", "b")),
    ]}
    result = parse_photon(payload)
    assert [r["name"] for r in result] == ["Ok"]
    assert result[0]["bbox"] is None
    assert result[0]["sub"] == "A, B"
    assert len(parse_photon({"features": [feature(f"P{i}") for i in range(8)]})) == 5
    assert parse_photon({}) == []


class Fakes:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []
        self.starts = []
        self.headers = None

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    async def fetch(self, url, headers):
        self.starts.append(self.now)
        self.headers = headers
        return 200, json.dumps(NARVIK)


async def test_client_spaces_requests_one_second():
    fakes = Fakes()
    client = PhotonClient("me@example.org", fetch=fakes.fetch, clock=fakes.clock, sleep=fakes.sleep)
    await asyncio.gather(client.search("a"), client.search("b"))
    assert fakes.starts[1] - fakes.starts[0] >= 1.0


async def test_client_sends_user_agent():
    fakes = Fakes()
    client = PhotonClient("me@example.org", fetch=fakes.fetch, clock=fakes.clock, sleep=fakes.sleep)
    result = await client.search("Narvik")
    assert fakes.headers["User-Agent"] == build_user_agent("me@example.org")
    assert len(result) == 2

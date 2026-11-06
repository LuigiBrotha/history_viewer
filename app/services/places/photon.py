import asyncio
import json
import math
import time
from typing import Annotated
from urllib.parse import urlencode

import requests
from wireup import Inject, injectable

from app.services.scraping.uboat_net.http_client import build_user_agent

PHOTON_URL = "https://photon.komoot.io/api/"
MAX_RESULTS = 5
MIN_INTERVAL = 1.0
TIMEOUT_SECONDS = 20


class PhotonError(Exception):
    pass


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_point(lat, lng) -> bool:
    return _number(lat) and _number(lng) and abs(lat) <= 90 and abs(lng) <= 180


def parse_photon(payload: dict) -> list[dict]:
    """At most 5 {name, sub, lat, lng, bbox}; features without a name or usable point are skipped."""
    results = []
    features = payload.get("features") if isinstance(payload, dict) else None
    for feature in features if isinstance(features, list) else []:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        props = props if isinstance(props, dict) else {}
        name = props.get("name")
        geometry = feature.get("geometry")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(name, str) or not name:
            continue
        if not (isinstance(coordinates, list) and len(coordinates) == 2 and _valid_point(coordinates[1], coordinates[0])):
            continue
        extent = props.get("extent")
        bbox = None
        if isinstance(extent, list) and len(extent) == 4:
            west, north, east, south = extent
            if _valid_point(north, west) and _valid_point(south, east):
                bbox = [south, north, west, east]
        sub = ", ".join(props[key] for key in ("city", "county", "state", "country")
                        if isinstance(props.get(key), str) and props[key])
        results.append({"name": name, "sub": sub, "lat": coordinates[1], "lng": coordinates[0], "bbox": bbox})
        if len(results) == MAX_RESULTS:
            break
    return results


async def _default_fetch(url: str, headers: dict) -> tuple[int, str]:
    def get():
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        return response.status_code, response.text

    try:
        return await asyncio.to_thread(get)
    except requests.RequestException as error:
        raise PhotonError(str(error)) from error


@injectable
class PhotonClient:
    """Asks Photon for places, at most one request a second for the whole process."""

    def __init__(self, contact: Annotated[str, Inject(config="CRAWLER_CONTACT")],
                 fetch=None, clock=time.monotonic, sleep=asyncio.sleep):
        self._user_agent = build_user_agent(contact)
        self._fetch = fetch or _default_fetch
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def search(self, query: str) -> list[dict]:
        url = PHOTON_URL + "?" + urlencode({"q": query, "limit": MAX_RESULTS, "lang": "en"})
        async with self._lock:
            if self._last is not None:
                wait = self._last + MIN_INTERVAL - self._clock()
                if wait > 0:
                    await self._sleep(wait)
            try:
                status, body = await self._fetch(url, {"User-Agent": self._user_agent})
            finally:
                self._last = self._clock()
        if status != 200:
            raise PhotonError(f"Photon answered {status}")
        try:
            return parse_photon(json.loads(body))
        except ValueError as error:
            raise PhotonError("Photon sent bad JSON") from error

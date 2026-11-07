import asyncio
import json
import math
import time
from typing import Annotated
from urllib.parse import urlencode

import requests
from wireup import Inject, injectable

from app.services.scraping.uboat_net.http_client import build_user_agent

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MAX_RESULTS = 5
MIN_INTERVAL = 1.0
TIMEOUT_SECONDS = 20


class PlaceSearchError(Exception):
    pass


def _coordinate(value, limit):
    """A float within ±limit from Nominatim's text, or None."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and abs(number) <= limit else None


def parse_nominatim(payload) -> list[dict]:
    """At most 5 {name, sub, lat, lng, bbox}; places without a usable point are skipped."""
    results = []
    for found in payload if isinstance(payload, list) else []:
        if not isinstance(found, dict):
            continue
        lat, lng = _coordinate(found.get("lat"), 90), _coordinate(found.get("lon"), 180)
        if lat is None or lng is None:
            continue
        parts = [p.strip() for p in str(found.get("display_name") or "").split(",") if p.strip()]
        name = found.get("name") if isinstance(found.get("name"), str) and found.get("name") else None
        if name is None:
            if not parts:
                continue
            name = parts[0]
        sub = ", ".join(parts[1:] if parts and parts[0] == name else parts)
        box = found.get("boundingbox")
        bbox = None
        if isinstance(box, list) and len(box) == 4:
            south, north = _coordinate(box[0], 90), _coordinate(box[1], 90)
            west, east = _coordinate(box[2], 180), _coordinate(box[3], 180)
            if None not in (south, north, west, east):
                bbox = [south, north, west, east]
        results.append({"name": name, "sub": sub, "lat": lat, "lng": lng, "bbox": bbox})
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
        raise PlaceSearchError(str(error)) from error


@injectable
class NominatimClient:
    """Asks OpenStreetMap's Nominatim for places, at most one request a second for the whole
    process, as its usage policy asks. Answers are cached by the caller."""

    def __init__(self, contact: Annotated[str, Inject(config="CRAWLER_CONTACT")],
                 fetch=None, clock=time.monotonic, sleep=asyncio.sleep):
        self._user_agent = build_user_agent(contact)
        self._fetch = fetch or _default_fetch
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def search(self, query: str) -> list[dict]:
        url = NOMINATIM_URL + "?" + urlencode(
            {"q": query, "format": "jsonv2", "limit": MAX_RESULTS, "accept-language": "nl,en"}
        )
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
            raise PlaceSearchError(f"Nominatim answered {status}")
        try:
            return parse_nominatim(json.loads(body))
        except ValueError as error:
            raise PlaceSearchError("Nominatim sent bad JSON") from error

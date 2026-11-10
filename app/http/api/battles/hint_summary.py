import asyncio
import json
import math
from functools import lru_cache

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup.integration.fastapi import WireupRoute

from app.services.storage.models import BattleHints

EARTH_KM = 6371.0
KEEP_SHARE = 0.9  # of the Plaatshints, those nearest each other make the Voorzet
MAX_STARTS = 20  # places tried as a starting point for those nearest each other


class HintSummaryOut(BaseModel):
    count: int
    lat: float
    lng: float
    spread_km: float
    voorzet_lat: float
    voorzet_lng: float


def _distance_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(min(1.0, h)))


def _unit(hint):
    lat, lng = math.radians(hint["lat"]), math.radians(hint["lng"])
    return math.cos(lat) * math.cos(lng), math.cos(lat) * math.sin(lng), math.sin(lat)


def _mean(vectors):
    return tuple(sum(vector[axis] for vector in vectors) / len(vectors) for axis in range(3))


def _distance_sq(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _tightest(vectors, keep):
    """The `keep` vectors with the smallest spread around their own mean: from several starting
    points, take the nearest, move to their mean and repeat; each round can only lower the spread."""
    step = max(1, len(vectors) // MAX_STARTS)
    best, best_score = None, math.inf
    for start in [_mean(vectors), *vectors[::step]]:
        center, chosen = start, None
        while True:
            nearest = sorted(range(len(vectors)), key=lambda i: _distance_sq(vectors[i], center))[:keep]
            if set(nearest) == chosen:
                break
            chosen = set(nearest)
            center = _mean([vectors[i] for i in nearest])
        score = sum(_distance_sq(vectors[i], center) for i in chosen)
        if score < best_score - 1e-12:
            best, best_score = [vectors[i] for i in sorted(chosen)], score
    return best


def voorzet(hints) -> tuple[float, float]:
    """The Voorzet of a Veldslag: the centre of gravity of the 90% of its Plaatshints that lie
    closest together (rounded to the nearest whole place, so five places keep four)."""
    vectors = [_unit(hint) for hint in hints]
    keep = max(1, math.ceil(KEEP_SHARE * len(vectors) - 0.5))
    x, y, z = _mean(_tightest(vectors, keep) if keep < len(vectors) else vectors)
    return round(math.degrees(math.atan2(z, math.hypot(x, y))), 6), round(math.degrees(math.atan2(y, x)), 6)


def summarise(hints) -> HintSummaryOut:
    """The middle of the hints (the mean of their unit vectors) and their standard deviation
    around it, in km."""
    x = y = z = 0.0
    for hint in hints:
        lat, lng = math.radians(hint["lat"]), math.radians(hint["lng"])
        x += math.cos(lat) * math.cos(lng)
        y += math.cos(lat) * math.sin(lng)
        z += math.sin(lat)
    lat = math.degrees(math.atan2(z, math.hypot(x, y)))
    lng = math.degrees(math.atan2(y, x))
    spread = math.sqrt(sum(_distance_km(h["lat"], h["lng"], lat, lng) ** 2 for h in hints) / len(hints))
    voorzet_lat, voorzet_lng = voorzet(hints)
    return HintSummaryOut(count=len(hints), lat=lat, lng=lng, spread_km=spread, voorzet_lat=voorzet_lat,
                          voorzet_lng=voorzet_lng)


@lru_cache(maxsize=20_000)
def _summary_of(hints_json: str) -> HintSummaryOut | None:
    hints = json.loads(hints_json)
    return summarise(hints) if hints else None


def _summaries(rows) -> dict[str, HintSummaryOut]:
    found = ((battle, _summary_of(hints_json)) for battle, hints_json in rows)
    return {battle: summary for battle, summary in found if summary is not None}


class RequestHandler:
    """Per Veldslag with Plaatshints: how many, their middle their spread and their Voorzet, so
    the list can show how far each battle's position lies from the places its articles name."""

    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    @router.get("/api/battles/hint-summary", name="battles_hint_summary")
    async def handle_request(self) -> dict[str, HintSummaryOut]:
        async with self.session_factory() as session:
            rows = (await session.execute(select(BattleHints.battle, BattleHints.hints_json))).all()
        # The first time takes seconds (see _tightest), so not on the event loop.
        return await asyncio.to_thread(_summaries, rows)

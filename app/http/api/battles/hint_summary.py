import json
import math
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.storage.models import BattleHints

EARTH_KM = 6371.0


class HintSummaryOut(BaseModel):
    count: int
    lat: float
    lng: float
    spread_km: float


def _distance_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(min(1.0, h)))


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
    return HintSummaryOut(count=len(hints), lat=lat, lng=lng, spread_km=spread)


class RequestHandler:
    """Per Veldslag with Plaatshints: how many, their middle and their spread, so the list can
    show how far each battle's position lies from the places its articles name."""

    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/battles/hint-summary", name="battles_hint_summary")
    async def handle_request(self) -> dict[str, HintSummaryOut]:
        async with self.session_factory() as session:
            rows = (await session.execute(select(BattleHints.battle, BattleHints.hints_json))).all()
        summary = {}
        for battle, hints_json in rows:
            hints = json.loads(hints_json)
            if hints:
                summary[battle] = summarise(hints)
        return summary

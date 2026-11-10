from datetime import datetime

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import ShipHitOut
from app.services.storage.ship_hit_repository import ShipHitRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    @router.get("/api/uboats/ships", name="uboats_ships")
    async def handle_request(self, since: datetime | None = None) -> list[ShipHitOut]:
        async with self.session_factory() as session:
            return await ShipHitRepository(session).list_hits(since=since)

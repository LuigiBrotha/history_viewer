from typing import Annotated

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import ShipDetailOut
from app.services.storage.ship_detail_repository import ShipDetailRepository
from app.services.storage.ship_hit_repository import ShipHitRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/ships/{ship_external_id}", name="uboats_ship_detail")
    async def handle_request(self, ship_external_id: str) -> ShipDetailOut:
        async with self.session_factory() as session:
            hits = await ShipHitRepository(session).list_hits(ship_external_id=ship_external_id)
            if not hits:
                raise HTTPException(status_code=404, detail="Ship not found")
            details = await ShipDetailRepository(session).get(ship_external_id)
        return ShipDetailOut(ship_external_id=ship_external_id, details=details, hits=hits)

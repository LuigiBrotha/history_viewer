from typing import Annotated

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import BoatDetail
from app.services.storage.boat_repository import BoatRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/boten/{slug}", name="uboats_boot_detail")
    async def handle_request(self, slug: str) -> BoatDetail:
        async with self.session_factory() as session:
            detail = await BoatRepository(session).get_detail(slug)
        if detail is None:
            raise HTTPException(status_code=404, detail="Boat not found")
        return detail

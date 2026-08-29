from typing import Annotated

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import BoatSummary
from app.services.storage.boat_repository import BoatRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/boten", name="uboats_boten_lijst")
    async def handle_request(self) -> list[BoatSummary]:
        async with self.session_factory() as session:
            return await BoatRepository(session).list_summaries()

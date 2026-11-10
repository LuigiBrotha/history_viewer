
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import PatrolPeriodOut
from app.services.storage.patrol_repository import PatrolRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    @router.get("/api/uboats/patrol-periods", name="uboats_patrol_periods")
    async def handle_request(self) -> list[PatrolPeriodOut]:
        async with self.session_factory() as session:
            return await PatrolRepository(session).list_periods()

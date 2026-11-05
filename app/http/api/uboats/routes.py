from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import PatrolRouteOut
from app.services.storage.patrol_repository import PatrolRepository

MAX_PAGE_SIZE = 1000


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/routes", name="uboats_routes")
    async def handle_request(
        self,
        since: datetime | None = None,
        limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[PatrolRouteOut]:
        async with self.session_factory() as session:
            return await PatrolRepository(session).list_routes(since=since, limit=limit, offset=offset)

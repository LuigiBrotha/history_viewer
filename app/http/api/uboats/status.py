from typing import Annotated

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import CrawlStatusOut
from app.services.storage.crawl_status_repository import CrawlStatusRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/status", name="uboats_status")
    async def handle_request(self) -> CrawlStatusOut:
        async with self.session_factory() as session:
            return await CrawlStatusRepository(session).get_status()

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.http.loopback import is_loopback
from app.services.export.uboats import CrawlStatusOut
from app.services.storage.crawl_status_repository import CrawlStatusRepository


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.get("/api/uboats/status", name="uboats_status")
    async def handle_request(self, request: Request = None) -> CrawlStatusOut:
        async with self.session_factory() as session:
            status = await CrawlStatusRepository(session).get_status()
        return replace(status, can_edit=is_loopback(request))

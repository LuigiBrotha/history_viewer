from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import PatrolRouteOut
from app.services.storage.patrol_repository import PatrolRepository
from app.services.storage.route_cache import RouteCache

MAX_PAGE_SIZE = 1000
_ROUTES_JSON = TypeAdapter(list[PatrolRouteOut])


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(
        self,
        session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()],
        cache: Annotated[RouteCache, Inject()],
    ):
        self.session_factory = session_factory
        self.cache = cache

    @router.get("/api/uboats/routes", name="uboats_routes", response_model=list[PatrolRouteOut])
    async def handle_request(
        self,
        since: datetime | None = None,
        limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> Response:
        if since is None:
            content = await self.cache.page(limit=limit, offset=offset)
        else:
            async with self.session_factory() as session:
                routes = await PatrolRepository(session).list_routes(since=since, limit=limit, offset=offset)
            content = _ROUTES_JSON.dump_json(routes)
        return Response(content=content, media_type="application/json")

import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.compute_water_routes import compute_routes_for_points
from app.http.loopback import require_loopback
from app.services.export.uboats import PatrolRouteOut
from app.services.storage.patrol_repository import (
    LastPointError,
    PatrolNotFound,
    PatrolRepository,
    PointNotFound,
)


class ExcludedPointIn(BaseModel):
    sequence: int


async def load_route_leg():
    """The routing engine, or None when it cannot be imported. Imported lazily: it needs geo libraries."""
    def load():
        try:
            from app.routing_engine.water_router import route_leg
        except Exception as exc:
            print(f"  ROUTING UNAVAILABLE: {exc}")
            return None
        return route_leg

    return await asyncio.to_thread(load)


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()]):
        self.session_factory = session_factory

    @router.post("/api/uboats/routes/{external_id}/excluded-points", name="uboats_exclude_point")
    async def exclude(self, request: Request, external_id: str, body: ExcludedPointIn) -> PatrolRouteOut:
        require_loopback(request)
        async with self.session_factory() as session:
            await self._edit(PatrolRepository(session).exclude_point, external_id, body.sequence)
        return await self._route_after_edit(external_id)

    @router.delete("/api/uboats/routes/{external_id}/excluded-points", name="uboats_restore_point")
    async def restore(self, request: Request, external_id: str, body: ExcludedPointIn) -> PatrolRouteOut:
        require_loopback(request)
        async with self.session_factory() as session:
            await self._edit(PatrolRepository(session).restore_point, external_id, body.sequence)
        return await self._route_after_edit(external_id)

    @staticmethod
    async def _edit(action, external_id: str, sequence: int) -> None:
        try:
            await action(external_id, sequence)
        except (PatrolNotFound, PointNotFound) as exc:
            raise HTTPException(status_code=404, detail="Unknown patrol or point") from exc
        except LastPointError as exc:
            raise HTTPException(status_code=409, detail="A route needs at least one point") from exc

    async def _route_after_edit(self, external_id: str) -> PatrolRouteOut:
        async with self.session_factory() as session:
            route = await PatrolRepository(session).get_route(external_id)
        route_leg = await load_route_leg()
        if route_leg is not None:
            # Never raises for routing failures: a failed leg stays not_computed.
            added = await compute_routes_for_points(route.points, self.session_factory, route_leg)
            if added:
                async with self.session_factory() as session:
                    repo = PatrolRepository(session)
                    await repo.touch(external_id)
                    route = await repo.get_route(external_id)
        return route

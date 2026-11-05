import asyncio
from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import injectable

from app.services.export.uboats import PatrolRouteOut
from app.services.storage.models import Patrol
from app.services.storage.patrol_repository import PatrolRepository

_ROUTE_JSON = TypeAdapter(PatrolRouteOut)


@injectable
class RouteCache:
    """All patrol routes as ready JSON, so that loading a page need not rebuild them.

    Building them from the database takes seconds at full scale. Only patrols changed since
    the last read are rebuilt, found through updated_at, which every change to what the maps
    show moves on.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._lock = asyncio.Lock()
        self._loaded = False
        self._revision: datetime | None = None
        self._entries: dict[str, tuple[tuple, bytes]] = {}
        self._ordered: list[bytes] = []

    async def page(self, limit: int | None = None, offset: int = 0) -> bytes:
        await self.refresh()
        end = None if limit is None else offset + limit
        return b"[" + b",".join(self._ordered[offset:end]) + b"]"

    async def refresh(self) -> None:
        async with self._lock:
            async with self._session_factory() as session:
                # Read before the routes: a patrol stored in between is simply read again later.
                revision, count = (await session.execute(
                    select(func.max(Patrol.updated_at), func.count(Patrol.id))
                )).one()
                if self._loaded and revision == self._revision and count == len(self._entries):
                    return
                # Patrols without a timestamp are only found by a full read.
                since = self._revision if self._loaded else None
                routes = await PatrolRepository(session).list_routes(since=since)
            for route in routes:
                key = (route.boat_slug, route.patrol_number, route.external_id)
                self._entries[route.external_id] = (key, _ROUTE_JSON.dump_json(route))
            self._ordered = [entry[1] for entry in sorted(self._entries.values(), key=lambda entry: entry[0])]
            self._revision = revision
            self._loaded = True

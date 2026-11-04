import json

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.routing.types import LatLng, RoutedLeg
from app.services.storage.models import WaterRoute

Pair = tuple[LatLng, LatLng]

# Four parameters per pair; SQLite allows 999 variables in older builds.
CHUNK_SIZE = 200


class WaterRouteRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, start: LatLng, end: LatLng, leg: RoutedLeg) -> None:
        values = dict(
            from_lat=start[0], from_lng=start[1], to_lat=end[0], to_lng=end[1],
            status=leg.status,
            path=json.dumps(leg.path) if leg.path is not None else None,
            length_km=leg.length_km,
        )
        stmt = insert(WaterRoute).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["from_lat", "from_lng", "to_lat", "to_lng"],
            set_={key: stmt.excluded[key] for key in ("status", "path", "length_km")},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_many(self, pairs: list[Pair]) -> dict[Pair, RoutedLeg]:
        unique = list(dict.fromkeys(pairs))
        found: dict[Pair, RoutedLeg] = {}
        for i in range(0, len(unique), CHUNK_SIZE):
            chunk = unique[i:i + CHUNK_SIZE]
            condition = or_(*(
                and_(
                    WaterRoute.from_lat == s[0], WaterRoute.from_lng == s[1],
                    WaterRoute.to_lat == e[0], WaterRoute.to_lng == e[1],
                )
                for s, e in chunk
            ))
            result = await self._session.execute(select(WaterRoute).where(condition))
            for row in result.scalars():
                path = [tuple(p) for p in json.loads(row.path)] if row.path is not None else None
                found[((row.from_lat, row.from_lng), (row.to_lat, row.to_lng))] = RoutedLeg(
                    row.status, path, row.length_km
                )
        return found

    async def missing(self, pairs: list[Pair], force: bool = False) -> list[Pair]:
        unique = list(dict.fromkeys(pairs))
        if force:
            return unique
        existing = await self.get_many(unique)
        return [pair for pair in unique if pair not in existing]

import json

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.routing.types import LatLng, RoutedLeg
from app.services.storage.models import WaterRoute

Pair = tuple[LatLng, LatLng]

# Four parameters per pair; SQLite allows 999 variables in older builds.
LATITUDE_CHUNK_SIZE = 500
# Above this many unique pairs, thousands of OR-ed conditions cost more than reading the table once.
FULL_READ_THRESHOLD = 2000


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
        if len(unique) > FULL_READ_THRESHOLD:
            wanted = set(unique)
            result = await self._session.execute(select(
                WaterRoute.from_lat, WaterRoute.from_lng, WaterRoute.to_lat, WaterRoute.to_lng,
                WaterRoute.status, WaterRoute.path, WaterRoute.length_km,
            ))
            for from_lat, from_lng, to_lat, to_lng, status, path, length_km in result:
                pair = ((from_lat, from_lng), (to_lat, to_lng))
                if pair in wanted:
                    found[pair] = self._to_leg(status, path, length_km)
            return found
        # The primary key starts with from_lat, and positions share few distinct latitudes,
        # so this reads far less than the whole table and stays well under the variable limit.
        wanted = set(unique)
        latitudes = list({start[0] for start, _ in unique})
        for i in range(0, len(latitudes), LATITUDE_CHUNK_SIZE):
            result = await self._session.execute(select(
                WaterRoute.from_lat, WaterRoute.from_lng, WaterRoute.to_lat, WaterRoute.to_lng,
                WaterRoute.status, WaterRoute.path, WaterRoute.length_km,
            ).where(WaterRoute.from_lat.in_(latitudes[i:i + LATITUDE_CHUNK_SIZE])))
            for from_lat, from_lng, to_lat, to_lng, status, path, length_km in result:
                pair = ((from_lat, from_lng), (to_lat, to_lng))
                if pair in wanted:
                    found[pair] = self._to_leg(status, path, length_km)
        return found

    @staticmethod
    def _to_leg(status: str, path: str | None, length_km: float | None) -> RoutedLeg:
        points = [tuple(p) for p in json.loads(path)] if path is not None else None
        return RoutedLeg(status, points, length_km)

    async def missing(self, pairs: list[Pair], force: bool = False) -> list[Pair]:
        unique = list(dict.fromkeys(pairs))
        if force:
            return unique
        existing = await self.get_many(unique)
        return [pair for pair in unique if pair not in existing]

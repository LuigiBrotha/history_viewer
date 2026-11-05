from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import PatrolRouteOut, RoutePointOut
from app.services.routing.approximate_dates import with_approximate_dates
from app.services.routing.legs import build_legs
from app.services.scraping.uboat_net.types import PatrolDetail, PatrolSummary
from app.services.storage.models import Boat, ExcludedRoutePoint, Patrol, RoutePoint
from app.services.storage.water_route_repository import WaterRouteRepository


class PatrolNotFound(Exception):
    pass


class PointNotFound(Exception):
    pass


class LastPointError(Exception):
    """Excluding the point would leave the patrol without a visible point."""


def _exclusion_keys(points) -> list[tuple[float, float, int]]:
    """One key per source row, in the order given: (lat, lng, 0-based ordinal among rows with those coordinates)."""
    seen: dict[tuple[float, float], int] = {}
    keys = []
    for pt in points:
        coords = (pt.lat, pt.lng)
        keys.append((*coords, seen.get(coords, 0)))
        seen[coords] = seen.get(coords, 0) + 1
    return keys


class PatrolRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_patrol(self, boat_id: int, summary: PatrolSummary, detail: PatrolDetail) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(Patrol).values(
            boat_id=boat_id,
            external_id=summary.external_id,
            patrol_number=summary.patrol_number,
            commander=summary.commander,
            departure_port=summary.departure_port,
            departure_date=summary.departure_date,
            arrival_port=summary.arrival_port,
            arrival_date=summary.arrival_date,
            days_at_sea=summary.days_at_sea,
            tonnage=summary.tonnage,
            description=detail.description,
            crawled_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "boat_id": stmt.excluded.boat_id,
                "patrol_number": stmt.excluded.patrol_number,
                "commander": stmt.excluded.commander,
                "departure_port": stmt.excluded.departure_port,
                "departure_date": stmt.excluded.departure_date,
                "arrival_port": stmt.excluded.arrival_port,
                "arrival_date": stmt.excluded.arrival_date,
                "days_at_sea": stmt.excluded.days_at_sea,
                "tonnage": stmt.excluded.tonnage,
                "description": stmt.excluded.description,
                "crawled_at": now,
                "updated_at": now,
            },
        )
        await self._session.execute(stmt)

        patrol_id = await self._session.scalar(
            select(Patrol.id).where(Patrol.external_id == summary.external_id)
        )

        await self._session.execute(delete(RoutePoint).where(RoutePoint.patrol_id == patrol_id))
        for point in detail.route_points:
            self._session.add(RoutePoint(
                patrol_id=patrol_id,
                sequence=point.sequence,
                lat=point.lat,
                lng=point.lng,
                date=point.date,
            ))
        await self._session.commit()

    async def touch(self, external_id: str) -> None:
        """Mark a patrol as changed so pollers refetch it; crawled_at is left alone."""
        # Taken right before the write: the revision cursor uses max(updated_at),
        # and an earlier timestamp could fall behind a poll that already happened.
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(Patrol).where(Patrol.external_id == external_id).values(updated_at=now)
        )
        await self._session.commit()

    async def exclude_point(self, external_id: str, sequence: int) -> tuple[float, float]:
        """Hide a route point; the source row stays. Returns its (lat, lng)."""
        points = await self._source_points(external_id)
        target = self._find(points, sequence)
        keys = _exclusion_keys(points)
        key = keys[points.index(target)]
        excluded = await self._excluded_keys(external_id)
        if not any(k != key and k not in excluded for k in keys):
            raise LastPointError(external_id)
        # Taken right before the write, like touch().
        now = datetime.now(timezone.utc)
        await self._session.execute(
            insert(ExcludedRoutePoint)
            .values(external_id=external_id, lat=key[0], lng=key[1], occurrence=key[2])
            .on_conflict_do_nothing()
        )
        await self._bump(external_id, now)
        return target.lat, target.lng

    async def restore_point(self, external_id: str, sequence: int) -> None:
        """Show an excluded point again; sequence is the source row's. No-op if not excluded."""
        points = await self._source_points(external_id)
        target = self._find(points, sequence)
        key = _exclusion_keys(points)[points.index(target)]
        now = datetime.now(timezone.utc)
        await self._session.execute(
            delete(ExcludedRoutePoint).where(
                ExcludedRoutePoint.external_id == external_id,
                ExcludedRoutePoint.lat == key[0],
                ExcludedRoutePoint.lng == key[1],
                ExcludedRoutePoint.occurrence == key[2],
            )
        )
        await self._bump(external_id, now)

    async def _source_points(self, external_id: str) -> list[RoutePoint]:
        patrol_id = await self._session.scalar(select(Patrol.id).where(Patrol.external_id == external_id))
        if patrol_id is None:
            raise PatrolNotFound(external_id)
        result = await self._session.execute(
            select(RoutePoint).where(RoutePoint.patrol_id == patrol_id).order_by(RoutePoint.sequence)
        )
        return list(result.scalars().all())

    @staticmethod
    def _find(points: list[RoutePoint], sequence: int) -> RoutePoint:
        for pt in points:
            if pt.sequence == sequence:
                return pt
        raise PointNotFound(sequence)

    async def _excluded_keys(self, external_id: str) -> set[tuple[float, float, int]]:
        result = await self._session.execute(
            select(ExcludedRoutePoint.lat, ExcludedRoutePoint.lng, ExcludedRoutePoint.occurrence)
            .where(ExcludedRoutePoint.external_id == external_id)
        )
        return {(lat, lng, occurrence) for lat, lng, occurrence in result.all()}

    async def _bump(self, external_id: str, now: datetime) -> None:
        await self._session.execute(
            update(Patrol).where(Patrol.external_id == external_id).values(updated_at=now)
        )
        await self._session.commit()

    async def get_route(self, external_id: str) -> PatrolRouteOut:
        routes = await self._routes(external_id=external_id)
        if not routes:
            raise PatrolNotFound(external_id)
        return routes[0]

    async def list_routes(
        self, since: datetime | None = None, limit: int | None = None, offset: int = 0
    ) -> list[PatrolRouteOut]:
        return await self._routes(since=since, limit=limit, offset=offset)

    async def _routes(
        self,
        since: datetime | None = None,
        external_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PatrolRouteOut]:
        stmt = (
            select(Patrol, Boat.slug, Boat.number)
            .join(Boat, Patrol.boat_id == Boat.id)
            .order_by(Boat.slug, Patrol.patrol_number, Patrol.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        if since is not None:
            stmt = stmt.where(Patrol.updated_at >= since)
        if external_id is not None:
            stmt = stmt.where(Patrol.external_id == external_id)
        result = await self._session.execute(stmt)
        rows = result.all()

        # Fetch every route point for every patrol in one query instead of one
        # SELECT per patrol (an N+1 that's invisible at 43 patrols but becomes
        # ~5000 sequential awaits at full ~1153-boat scale).
        patrol_ids = [patrol.id for patrol, _, _ in rows]
        points_by_patrol_id: dict[int, list[RoutePoint]] = {}
        excluded_keys: dict[str, set[tuple[float, float, int]]] = {}
        if patrol_ids:
            # Exclusions in one query as well, and not an IN list: it can run to thousands of ids.
            external_ids = {patrol.external_id for patrol, _, _ in rows}
            excluded_result = await self._session.execute(select(ExcludedRoutePoint))
            for ex in excluded_result.scalars().all():
                if ex.external_id in external_ids:
                    excluded_keys.setdefault(ex.external_id, set()).add((ex.lat, ex.lng, ex.occurrence))
            points_result = await self._session.execute(
                select(RoutePoint)
                .where(RoutePoint.patrol_id.in_(patrol_ids))
                .order_by(RoutePoint.patrol_id, RoutePoint.sequence)
            )
            for point in points_result.scalars().all():
                points_by_patrol_id.setdefault(point.patrol_id, []).append(point)

        split: dict[int, tuple[list[RoutePointOut], list[RoutePointOut]]] = {}
        for patrol, _, _ in rows:
            hidden = excluded_keys.get(patrol.external_id, set())
            visible, excluded = [], []
            source = points_by_patrol_id.get(patrol.id, [])
            for pt, key in zip(source, _exclusion_keys(source)):
                out = RoutePointOut(sequence=pt.sequence, lat=pt.lat, lng=pt.lng, date=pt.date)
                is_hidden = key in hidden
                (excluded if is_hidden else visible).append(out)
            split[patrol.id] = (visible, excluded)

        routes_by_pair = await WaterRouteRepository(self._session).get_many([
            pair
            for pts, _ in split.values()
            for pair in zip(
                ((pt.lat, pt.lng) for pt in pts),
                ((pt.lat, pt.lng) for pt in pts[1:]),
            )
        ])

        routes = []
        for patrol, boat_slug, boat_number in rows:
            points, excluded_points = split[patrol.id]
            routes.append(PatrolRouteOut(
                boat_slug=boat_slug,
                boat_number=boat_number,
                external_id=patrol.external_id,
                departure_date=patrol.departure_date,
                arrival_date=patrol.arrival_date,
                # Legs use the source dates: speed must never be judged on an approximation.
                points=with_approximate_dates(points, patrol.departure_date, patrol.arrival_date),
                legs=build_legs(points, routes_by_pair),
                excluded_points=excluded_points,
            ))
        return routes

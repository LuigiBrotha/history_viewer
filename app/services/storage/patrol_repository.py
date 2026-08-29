from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import PatrolRouteOut, RoutePointOut
from app.services.scraping.uboat_net.types import PatrolDetail, PatrolSummary
from app.services.storage.models import Boat, Patrol, RoutePoint


class PatrolRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_patrol(self, boat_id: int, summary: PatrolSummary, detail: PatrolDetail) -> None:
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

    async def list_routes(self) -> list[PatrolRouteOut]:
        stmt = (
            select(Patrol, Boat.slug, Boat.number)
            .join(Boat, Patrol.boat_id == Boat.id)
            .order_by(Boat.slug, Patrol.patrol_number)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        # Fetch every route point for every patrol in one query instead of one
        # SELECT per patrol (an N+1 that's invisible at 43 patrols but becomes
        # ~5000 sequential awaits at full ~1153-boat scale).
        patrol_ids = [patrol.id for patrol, _, _ in rows]
        points_by_patrol_id: dict[int, list[RoutePoint]] = {}
        if patrol_ids:
            points_result = await self._session.execute(
                select(RoutePoint)
                .where(RoutePoint.patrol_id.in_(patrol_ids))
                .order_by(RoutePoint.patrol_id, RoutePoint.sequence)
            )
            for point in points_result.scalars().all():
                points_by_patrol_id.setdefault(point.patrol_id, []).append(point)

        routes = []
        for patrol, boat_slug, boat_number in rows:
            points = [
                RoutePointOut(sequence=pt.sequence, lat=pt.lat, lng=pt.lng, date=pt.date)
                for pt in points_by_patrol_id.get(patrol.id, [])
            ]
            routes.append(PatrolRouteOut(
                boat_slug=boat_slug,
                boat_number=boat_number,
                external_id=patrol.external_id,
                departure_date=patrol.departure_date,
                arrival_date=patrol.arrival_date,
                points=points,
            ))
        return routes

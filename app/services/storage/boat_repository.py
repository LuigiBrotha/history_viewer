from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import BoatDetail, BoatSummary, PatrolSummaryOut
from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.models import Boat, Patrol


class BoatRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_boat(self, data: BoatData) -> None:
        stmt = insert(Boat).values(
            slug=data.slug,
            number=data.number,
            type=data.type,
            builder=data.builder,
            laid_down=data.laid_down,
            launched=data.launched,
            commissioned=data.commissioned,
            fate=data.fate,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={
                "number": stmt.excluded.number,
                "type": stmt.excluded.type,
                "builder": stmt.excluded.builder,
                "laid_down": stmt.excluded.laid_down,
                "launched": stmt.excluded.launched,
                "commissioned": stmt.excluded.commissioned,
                "fate": stmt.excluded.fate,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_id_by_slug(self, slug: str) -> int | None:
        result = await self._session.execute(select(Boat.id).where(Boat.slug == slug))
        return result.scalar_one_or_none()

    async def list_summaries(self) -> list[BoatSummary]:
        patrol_count = func.count(Patrol.id).label("patrol_count")
        stmt = (
            select(Boat.slug, Boat.number, Boat.type, Boat.fate, patrol_count)
            .outerjoin(Patrol, Patrol.boat_id == Boat.id)
            .group_by(Boat.id)
            .order_by(Boat.slug)
        )
        result = await self._session.execute(stmt)
        return [
            BoatSummary(slug=row.slug, number=row.number, type=row.type, fate=row.fate, patrol_count=row.patrol_count)
            for row in result.all()
        ]

    async def get_detail(self, slug: str) -> BoatDetail | None:
        boat_result = await self._session.execute(select(Boat).where(Boat.slug == slug))
        boat = boat_result.scalar_one_or_none()
        if boat is None:
            return None

        patrols_result = await self._session.execute(
            select(Patrol).where(Patrol.boat_id == boat.id).order_by(Patrol.patrol_number)
        )
        patrols = [
            PatrolSummaryOut(
                external_id=p.external_id,
                patrol_number=p.patrol_number,
                commander=p.commander,
                departure_port=p.departure_port,
                departure_date=p.departure_date,
                arrival_port=p.arrival_port,
                arrival_date=p.arrival_date,
                days_at_sea=p.days_at_sea,
                tonnage=p.tonnage,
            )
            for p in patrols_result.scalars().all()
        ]

        return BoatDetail(
            slug=boat.slug,
            number=boat.number,
            type=boat.type,
            builder=boat.builder,
            laid_down=boat.laid_down,
            launched=boat.launched,
            commissioned=boat.commissioned,
            fate=boat.fate,
            patrols=patrols,
        )

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import CrawlStatusOut, LastPatrolOut
from app.services.storage.models import Boat, BoatCrawlState, CrawlProgress, Patrol, ShipHit


class CrawlStatusRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def set_listing_total(self, total: int) -> None:
        stmt = insert(CrawlProgress).values(id=1, listing_total=total)
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_={"listing_total": total})
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_status(self) -> CrawlStatusOut:
        listing_total = await self._session.scalar(select(CrawlProgress.listing_total).where(CrawlProgress.id == 1))
        boats_crawled = await self._count_boats("success")
        boats_failed = await self._count_boats("failed")
        patrol_count = await self._session.scalar(select(func.count()).select_from(Patrol))
        revisions = [
            await self._session.scalar(select(func.max(Patrol.updated_at))),
            await self._session.scalar(select(func.max(ShipHit.updated_at))),
        ]
        revision = max((r for r in revisions if r is not None), default=None)

        last_row = (await self._session.execute(
            select(Boat.slug, Boat.number, Patrol.external_id, Patrol.crawled_at)
            .join(Boat, Patrol.boat_id == Boat.id)
            .where(Patrol.crawled_at.is_not(None))
            .order_by(Patrol.crawled_at.desc(), Patrol.id.desc())
            .limit(1)
        )).first()
        last_patrol = LastPatrolOut(*last_row) if last_row else None

        first_departure, last_departure = (await self._session.execute(
            select(func.min(Patrol.departure_date), func.max(Patrol.departure_date))
        )).one()

        return CrawlStatusOut(
            listing_total=listing_total,
            boats_crawled=boats_crawled,
            boats_failed=boats_failed,
            patrol_count=patrol_count,
            revision=revision,
            last_patrol=last_patrol,
            first_departure=first_departure,
            last_departure=last_departure,
        )

    async def _count_boats(self, status: str) -> int:
        return await self._session.scalar(
            select(func.count()).select_from(BoatCrawlState).where(BoatCrawlState.status == status)
        )

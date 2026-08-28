from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.storage.models import BoatCrawlState


class BoatCrawlStateRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def record_success(self, slug: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(BoatCrawlState).values(
            slug=slug, status="success", last_attempt_at=now, last_success_at=now, last_error=None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={"status": "success", "last_attempt_at": now, "last_success_at": now, "last_error": None},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def record_failure(self, slug: str, error: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(BoatCrawlState).values(
            slug=slug, status="failed", last_attempt_at=now, last_success_at=None, last_error=error,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["slug"],
            set_={"status": "failed", "last_attempt_at": now, "last_error": error},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get(self, slug: str) -> BoatCrawlState | None:
        result = await self._session.execute(select(BoatCrawlState).where(BoatCrawlState.slug == slug))
        return result.scalar_one_or_none()

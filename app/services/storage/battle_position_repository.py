from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.storage.models import BattlePosition


class BattlePositionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def all(self) -> list[tuple[str, float, float]]:
        rows = await self._session.execute(
            select(BattlePosition.title, BattlePosition.lat, BattlePosition.lng).order_by(BattlePosition.title)
        )
        return [(title, lat, lng) for title, lat, lng in rows]

    async def put(self, title: str, lat: float, lng: float) -> None:
        values = dict(title=title, lat=lat, lng=lng, updated_at=datetime.now(timezone.utc))
        stmt = insert(BattlePosition).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["title"],
            set_={key: stmt.excluded[key] for key in ("lat", "lng", "updated_at")},
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def delete(self, title: str) -> None:
        await self._session.execute(delete(BattlePosition).where(BattlePosition.title == title))
        await self._session.commit()

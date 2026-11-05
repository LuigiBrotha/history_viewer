from dataclasses import asdict, fields
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scraping.uboat_net.types import ShipDetails
from app.services.storage.models import ShipDetail

_FIELDS = [f.name for f in fields(ShipDetails)]


class ShipDetailRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, ship_external_id: str, details: ShipDetails) -> None:
        values = {**asdict(details), "updated_at": datetime.now(timezone.utc)}
        stmt = insert(ShipDetail).values(ship_external_id=ship_external_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=["ship_external_id"], set_=values)
        await self._session.execute(stmt)
        await self._session.commit()

    async def get(self, ship_external_id: str) -> ShipDetails | None:
        row = (
            await self._session.execute(
                select(ShipDetail)
                .where(ShipDetail.ship_external_id == ship_external_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return None if row is None else ShipDetails(**{name: getattr(row, name) for name in _FIELDS})

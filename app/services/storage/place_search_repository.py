import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.storage.models import PlaceSearch


class PlaceSearchRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, query: str) -> list | None:
        raw = await self._session.scalar(select(PlaceSearch.results_json).where(PlaceSearch.query == query))
        return None if raw is None else json.loads(raw)

    async def put(self, query: str, results: list) -> None:
        values = dict(query=query, results_json=json.dumps(results), fetched_at=datetime.now(timezone.utc))
        stmt = insert(PlaceSearch).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["query"],
            set_={key: stmt.excluded[key] for key in ("results_json", "fetched_at")},
        )
        await self._session.execute(stmt)
        await self._session.commit()

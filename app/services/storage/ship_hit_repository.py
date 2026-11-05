import re
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export.uboats import ShipHitOut
from app.services.scraping.uboat_net.types import ShipHitRef
from app.services.storage.models import Boat, ShipDetail, ShipHit

_SLUG_RE = re.compile(r"^([a-z]+)(\d+)$")

# What a re-crawl of the successes page may change; the position is never among them.
_REF_COLUMNS = ("name", "tons", "nationality", "convoy", "outcome", "detail_url")


def _number_from_slug(slug: str) -> str:
    match = _SLUG_RE.match(slug)
    return f"{match.group(1).upper()}-{match.group(2)}" if match else slug.upper()


class ShipHitRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_refs(self, refs: list[ShipHitRef]) -> None:
        """Store hits; one that already exists keeps its position and only moves when a value changed."""
        now = datetime.now(timezone.utc)
        for ref in refs:
            stmt = insert(ShipHit).values(
                ship_external_id=ref.ship_external_id,
                boat_slug=ref.boat_slug,
                date=ref.date,
                name=ref.name,
                tons=ref.tons,
                nationality=ref.nationality,
                convoy=ref.convoy,
                outcome=ref.outcome,
                detail_url=ref.detail_url,
                position_checked=False,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["ship_external_id", "boat_slug", "date"],
                set_={**{c: stmt.excluded[c] for c in _REF_COLUMNS}, "updated_at": now},
                where=or_(*(ShipHit.__table__.c[c].is_not(stmt.excluded[c]) for c in _REF_COLUMNS)),
            )
            await self._session.execute(stmt)
        await self._session.commit()

    async def pending_pages(self, force: bool = False, slugs: list[str] | None = None) -> list[ShipHit]:
        """Hits whose ship page is still to be fetched: position unchecked or ship without details."""
        # populate_existing: rows are written with core statements, so instances held by the session go stale.
        stmt = select(ShipHit).order_by(ShipHit.id).execution_options(populate_existing=True)
        if not force:
            has_details = select(ShipDetail.ship_external_id).where(
                ShipDetail.ship_external_id == ShipHit.ship_external_id
            )
            stmt = stmt.where(or_(ShipHit.position_checked.is_(False), ~has_details.exists()))
        if slugs is not None:
            stmt = stmt.where(ShipHit.boat_slug.in_(slugs))
        return list((await self._session.execute(stmt)).scalars())

    async def set_position(self, hit_id: int, position: tuple[float, float] | None) -> None:
        lat, lng = position if position is not None else (None, None)
        await self._session.execute(
            update(ShipHit)
            .where(ShipHit.id == hit_id)
            .values(lat=lat, lng=lng, position_checked=True, updated_at=datetime.now(timezone.utc))
        )
        await self._session.commit()

    async def list_hits(
        self, since: datetime | None = None, ship_external_id: str | None = None
    ) -> list[ShipHitOut]:
        stmt = (
            select(ShipHit, Boat.number)
            .outerjoin(Boat, Boat.slug == ShipHit.boat_slug)
            .order_by(ShipHit.date, ShipHit.id)
            .execution_options(populate_existing=True)
        )
        if since is not None:
            stmt = stmt.where(ShipHit.updated_at >= since)
        if ship_external_id is not None:
            stmt = stmt.where(ShipHit.ship_external_id == ship_external_id)
        rows = (await self._session.execute(stmt)).all()
        return [
            ShipHitOut(
                ship_external_id=hit.ship_external_id,
                boat_slug=hit.boat_slug,
                boat_number=number or _number_from_slug(hit.boat_slug),
                name=hit.name,
                date=hit.date,
                tons=hit.tons,
                nationality=hit.nationality,
                convoy=hit.convoy,
                outcome=hit.outcome,
                lat=hit.lat,
                lng=hit.lng,
                updated_at=hit.updated_at,
            )
            for hit, number in rows
        ]

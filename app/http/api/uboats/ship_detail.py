from dataclasses import asdict, replace
from typing import Annotated

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import ShipDetailOut
from app.services.storage.ship_detail_repository import ShipDetailRepository
from app.services.storage.ship_hit_repository import ShipHitRepository
from app.services.wiki.article_service import ArticleService

# The fields of a ship's page that are running English.
TRANSLATED = ("fate", "complement", "cargo", "history", "notes")


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(
        self,
        session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()],
        articles: Annotated[ArticleService, Inject()],
    ):
        self.session_factory = session_factory
        self.articles = articles

    @router.get("/api/uboats/ships/{ship_external_id}", name="uboats_ship_detail")
    async def handle_request(self, ship_external_id: str, versie: str = "origineel") -> ShipDetailOut:
        """The ship and its hits, with versie=nl its running text in Dutch where that can be made."""
        async with self.session_factory() as session:
            hits = await ShipHitRepository(session).list_hits(ship_external_id=ship_external_id)
            if not hits:
                raise HTTPException(status_code=404, detail="Ship not found")
            details = await ShipDetailRepository(session).get(ship_external_id)
        out = ShipDetailOut(ship_external_id=ship_external_id, details=details, hits=hits)
        return await self._dutch(out) if versie == "nl" and details is not None else out

    async def _dutch(self, out: ShipDetailOut) -> ShipDetailOut:
        fields = asdict(out.details)
        texts = {name: fields[name] for name in TRANSLATED}
        dutch = await self.articles.dutch_texts(f"ship:{out.ship_external_id}", texts)
        if dutch is None:
            return out
        return replace(out, details=replace(out.details, **dutch), translated=True)

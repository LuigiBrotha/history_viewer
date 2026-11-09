from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.export.uboats import BoatDetail
from app.services.storage.boat_repository import BoatRepository
from app.services.wiki.article_service import ArticleService


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(
        self,
        session_factory: Annotated[async_sessionmaker[AsyncSession], Inject()],
        articles: Annotated[ArticleService, Inject()],
    ):
        self.session_factory = session_factory
        self.articles = articles

    @router.get("/api/uboats/boten/{slug}", name="uboats_boot_detail")
    async def handle_request(self, slug: str, versie: str = "origineel") -> BoatDetail:
        """The boat, with versie=nl its running text in Dutch where that can be made."""
        async with self.session_factory() as session:
            detail = await BoatRepository(session).get_detail(slug)
        if detail is None:
            raise HTTPException(status_code=404, detail="Boat not found")
        return await self._dutch(detail) if versie == "nl" else detail

    async def _dutch(self, detail: BoatDetail) -> BoatDetail:
        texts = {"fate": detail.fate, **{f"patrol:{p.external_id}": p.description for p in detail.patrols}}
        dutch = await self.articles.dutch_texts(f"boat:{detail.slug}", texts)
        if dutch is None:
            return detail
        patrols = [replace(p, description=dutch.get(f"patrol:{p.external_id}", p.description)) for p in detail.patrols]
        return replace(detail, fate=dutch.get("fate", detail.fate), patrols=patrols, translated=True)

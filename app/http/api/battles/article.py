import re
from typing import Annotated

from fastapi import APIRouter, HTTPException
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.wiki.article_service import ArticleOut, ArticleService

# Any Wikipedia's code: the articles of every language may be stored (tools.wikidata_battles).
LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-z]+)?$")


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, articles: Annotated[ArticleService, Inject()]):
        self.articles = articles

    @router.get("/api/battles/articles/{title:path}", name="battles_article")
    async def handle_request(self, title: str, lang: str = "en", versie: str = "origineel") -> ArticleOut:
        """The Artikel in its own language, or with versie=nl its Dutch version."""
        if not LANGUAGE.match(lang):
            raise HTTPException(status_code=404, detail="Geen artikel voor deze veldslag.")
        if versie == "nl":
            if await self.articles.article(title, lang) is None:
                raise HTTPException(status_code=404, detail="Geen artikel voor deze veldslag.")
            article = await self.articles.dutch(title, lang)
            if article is None:
                raise HTTPException(status_code=404, detail="Geen Nederlandse versie voor dit artikel.")
            return article
        article = await self.articles.article(title, lang)
        if article is None:
            raise HTTPException(status_code=404, detail="Geen artikel voor deze veldslag.")
        return article

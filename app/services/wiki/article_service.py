from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import injectable

from app.services.storage.battle_article_repository import BattleArticleRepository
from app.services.wiki.render import render_article
from app.services.wiki.titles import wiki_url

CACHE_SIZE = 64


@dataclass
class ArticleOut:
    title: str
    html: str
    url: str


def _image_url(file_name: str, width: int) -> str:
    # Replaced by the cached image endpoint's helper once that exists.
    return f"/api/battles/images/{quote(file_name)}?width={width}"


@injectable
class ArticleService:
    """Rendered battle articles, with the last few kept so that reopening one costs nothing."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._battle_index: dict[str, str] = {}
        self._cache: OrderedDict[str, ArticleOut] = OrderedDict()

    async def article(self, title: str) -> ArticleOut | None:
        async with self._session_factory() as session:
            repository = BattleArticleRepository(session)
            found = await repository.get(title)
            if found is None:
                return None
            real_title, wikitext = found
            cached = self._cache.get(real_title)
            if cached is not None:
                self._cache.move_to_end(real_title)
                return cached
            if not self._battle_index:
                self._battle_index = await repository.battle_index()
        html = render_article(wikitext, battle_index=self._battle_index, image_src=_image_url)
        article = ArticleOut(real_title, html, wiki_url(real_title))
        self._cache[real_title] = article
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return article

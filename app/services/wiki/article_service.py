from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import injectable

from app.services.storage.battle_article_repository import BattleArticleRepository, ForeignBattleArticleRepository
from app.services.wiki.image_cache import image_url_for
from app.services.wiki.render import render_article
from app.services.wiki.titles import wiki_url

CACHE_SIZE = 64


@dataclass
class ArticleOut:
    title: str
    html: str
    url: str


@injectable
class ArticleService:
    """Rendered battle articles, with the last few kept so that reopening one costs nothing."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._battle_index: dict[str, dict[str, str]] = {}
        self._cache: OrderedDict[tuple[str, str], ArticleOut] = OrderedDict()

    async def article(self, title: str, lang: str = "en") -> ArticleOut | None:
        async with self._session_factory() as session:
            if lang == "en":
                repository = BattleArticleRepository(session)
            else:
                repository = ForeignBattleArticleRepository(session, lang)
            found = await repository.get(title)
            if found is None:
                return None
            real_title, wikitext = found
            cached = self._cache.get((lang, real_title))
            if cached is not None:
                self._cache.move_to_end((lang, real_title))
                return cached
            if lang not in self._battle_index:
                self._battle_index[lang] = await repository.battle_index()
        html = render_article(wikitext, battle_index=self._battle_index[lang], image_src=image_url_for, lang=lang)
        article = ArticleOut(real_title, html, wiki_url(real_title, lang))
        self._cache[(lang, real_title)] = article
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return article

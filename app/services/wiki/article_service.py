import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import injectable

from app.services.storage.battle_article_repository import BattleArticleRepository, ForeignBattleArticleRepository
from app.services.storage.models import DutchArticle
from app.services.translation.html import translate_html
from app.services.wiki.image_cache import image_url_for
from app.services.wiki.render import render_article
from app.services.wiki.titles import wiki_url

CACHE_SIZE = 64


@dataclass
class ArticleOut:
    title: str
    html: str
    url: str
    # "origineel", or for the Dutch version "wikipedia" (the Dutch article) or "vertaald".
    source: str = "origineel"
    # The language of the original article.
    from_lang: str = "en"
    # Whether a Dutch version can be had (only told with the original).
    dutch: bool = False


def _default_models():
    from app.services.translation.argos import Models

    return Models()


@injectable
class ArticleService:
    """Rendered battle articles, with the last few kept so that reopening one costs nothing,
    and their Dutch versions."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], models=None):
        self._session_factory = session_factory
        self._models = models
        self._battle_index: dict[str, dict[str, str]] = {}
        self._cache: OrderedDict[tuple[str, str], ArticleOut] = OrderedDict()
        self._busy: dict[tuple[str, str], asyncio.Lock] = {}

    @property
    def models(self):
        if self._models is None:
            self._models = _default_models()
        return self._models

    async def article(self, title: str, lang: str = "en") -> ArticleOut | None:
        found = await self._original(title, lang)
        if found is None:
            return None
        article, _ = found
        async with self._session_factory() as session:
            stored = await session.get(DutchArticle, (lang, article.title))
        dutch = lang != "nl" and (stored is not None or self.models.can_reach_dutch(lang))
        return ArticleOut(article.title, article.html, article.url, from_lang=lang, dutch=dutch)

    async def dutch(self, title: str, lang: str = "en") -> ArticleOut | None:
        """The Dutch version: the Dutch Wikipedia's article, else a translation made once and kept."""
        if lang == "nl":
            return None
        found = await self._original(title, lang)
        if found is None:
            return None
        original, _ = found
        key = (lang, original.title)
        lock = self._busy.setdefault(key, asyncio.Lock())
        async with lock:
            async with self._session_factory() as session:
                stored = await session.get(DutchArticle, key)
            if stored is not None:
                return await self._from_stored(stored, original)
            if not self.models.can_reach_dutch(lang):
                return None
            html = await asyncio.to_thread(translate_html, original.html, partial(self.models.to_dutch, lang))
            async with self._session_factory() as session:
                await session.merge(DutchArticle(lang=lang, title=original.title, kind="vertaald", nl_title=None,
                                                 content=html, made_at=datetime.now(timezone.utc)))
                await session.commit()
        return ArticleOut(original.title, html, original.url, source="vertaald", from_lang=lang)

    async def _from_stored(self, stored: DutchArticle, original: ArticleOut) -> ArticleOut:
        if stored.kind == "vertaald":
            return ArticleOut(original.title, stored.content, original.url, source="vertaald", from_lang=stored.lang)
        index = await self._index("nl")
        html = render_article(stored.content, battle_index=index, image_src=image_url_for, lang="nl")
        return ArticleOut(stored.nl_title, html, wiki_url(stored.nl_title, "nl"), source="wikipedia",
                          from_lang=stored.lang)

    async def _index(self, lang: str) -> dict[str, str]:
        if lang not in self._battle_index:
            async with self._session_factory() as session:
                self._battle_index[lang] = await self._repository(session, lang).battle_index()
        return self._battle_index[lang]

    @staticmethod
    def _repository(session, lang):
        return BattleArticleRepository(session) if lang == "en" else ForeignBattleArticleRepository(session, lang)

    async def _original(self, title: str, lang: str) -> tuple[ArticleOut, str] | None:
        async with self._session_factory() as session:
            found = await self._repository(session, lang).get(title)
        if found is None:
            return None
        real_title, wikitext = found
        cached = self._cache.get((lang, real_title))
        if cached is not None:
            self._cache.move_to_end((lang, real_title))
            return cached, wikitext
        index = await self._index(lang)
        html = render_article(wikitext, battle_index=index, image_src=image_url_for, lang=lang)
        article = ArticleOut(real_title, html, wiki_url(real_title, lang))
        self._cache[(lang, real_title)] = article
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return article, wikitext

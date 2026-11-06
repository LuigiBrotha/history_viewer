from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.storage.models import BattleArticle, BattleRedirect
from app.services.wiki.titles import normalize_title


class BattleArticleRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, title: str) -> tuple[str, str] | None:
        """Return (real title, wikitext) for a title, following at most one redirect."""
        normalized = normalize_title(title)
        article = await self._article(normalized)
        if article is not None:
            return article
        target = await self._session.scalar(
            select(BattleRedirect.title).where(BattleRedirect.alias == normalized)
        )
        if target is None:
            return None
        return await self._article(target)

    async def battle_index(self) -> dict[str, str]:
        """Map every normalised article title and redirect alias to the real article title."""
        index: dict[str, str] = {}
        for alias, title in (await self._session.execute(
            select(BattleRedirect.alias, BattleRedirect.title)
        )).all():
            index[normalize_title(alias)] = title
        for (title,) in (await self._session.execute(select(BattleArticle.title))).all():
            index[normalize_title(title)] = title
        return index

    async def _article(self, title: str) -> tuple[str, str] | None:
        row = (await self._session.execute(
            select(BattleArticle.title, BattleArticle.wikitext).where(BattleArticle.title == title)
        )).first()
        return (row[0], row[1]) if row else None

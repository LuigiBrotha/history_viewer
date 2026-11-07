from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.storage.models import BattleArticle, BattleRedirect, ForeignBattleArticle
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


class ForeignBattleArticleRepository:
    """Battle articles in another language than English, with the Veldslag each belongs to."""

    def __init__(self, session: AsyncSession, lang: str):
        self._session = session
        self._lang = lang

    async def get(self, title: str) -> tuple[str, str] | None:
        row = (await self._session.execute(
            select(ForeignBattleArticle.title, ForeignBattleArticle.wikitext).where(
                ForeignBattleArticle.lang == self._lang, ForeignBattleArticle.title == normalize_title(title)
            )
        )).first()
        return (row[0], row[1]) if row else None

    async def battle_index(self) -> dict[str, str]:
        """Map the normalised titles of this language's battle articles to their Veldslag."""
        rows = await self._session.execute(
            select(ForeignBattleArticle.title, ForeignBattleArticle.battle).where(
                ForeignBattleArticle.lang == self._lang, ForeignBattleArticle.battle.is_not(None)
            )
        )
        return {normalize_title(title): battle for title, battle in rows.all()}

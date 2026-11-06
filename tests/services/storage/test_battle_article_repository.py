from datetime import datetime, timezone

from app.services.storage.battle_article_repository import BattleArticleRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import BattleArticle, BattleRedirect


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return create_session_factory(engine)


async def _seed(session):
    session.add(BattleArticle(
        title="Second Happy Time", wikitext="'''Second Happy Time'''",
        dump_name="dump", extracted_at=datetime.now(timezone.utc),
    ))
    await session.flush()
    session.add(BattleRedirect(alias="Operation Drumbeat", title="Second Happy Time"))
    await session.commit()


async def test_get_finds_article_by_normalised_title(tmp_path):
    factory = await _session_factory(tmp_path)
    async with factory() as session:
        await _seed(session)
        result = await BattleArticleRepository(session).get("Second_Happy_Time")
    assert result == ("Second Happy Time", "'''Second Happy Time'''")


async def test_get_follows_one_redirect(tmp_path):
    factory = await _session_factory(tmp_path)
    async with factory() as session:
        await _seed(session)
        result = await BattleArticleRepository(session).get("Operation Drumbeat")
    assert result == ("Second Happy Time", "'''Second Happy Time'''")


async def test_get_unknown_returns_none(tmp_path):
    factory = await _session_factory(tmp_path)
    async with factory() as session:
        await _seed(session)
        assert await BattleArticleRepository(session).get("Unknown") is None


async def test_get_redirect_to_missing_article_returns_none(tmp_path):
    factory = await _session_factory(tmp_path)
    async with factory() as session:
        session.add(BattleRedirect(alias="Dangling", title="Not Stored"))
        await session.commit()
        assert await BattleArticleRepository(session).get("Dangling") is None


async def test_battle_index_maps_titles_and_aliases_to_real_title(tmp_path):
    factory = await _session_factory(tmp_path)
    async with factory() as session:
        await _seed(session)
        index = await BattleArticleRepository(session).battle_index()
    assert index == {
        "Second Happy Time": "Second Happy Time",
        "Operation Drumbeat": "Second Happy Time",
    }

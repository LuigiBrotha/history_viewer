from datetime import datetime, timezone
from urllib.parse import quote

import pytest
from fastapi import HTTPException

from app.http.api.battles.article import RequestHandler
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import BattleArticle, BattleRedirect
from app.services.wiki import article_service
from app.services.wiki.article_service import ArticleService

TITLES = ["Second Happy Time", 'Operation "Weserübung"', "Battle of the Bulge (1944–45)"]


@pytest.fixture
async def handler(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        for title in TITLES:
            session.add(BattleArticle(
                title=title, wikitext=f"'''{title}''' was a battle.",
                dump_name="dump", extracted_at=datetime.now(timezone.utc),
            ))
        await session.flush()
        session.add(BattleRedirect(alias="Operation Drumbeat", title="Second Happy Time"))
        await session.commit()
    yield RequestHandler(ArticleService(factory))
    await engine.dispose()


async def test_found_by_exact_title(handler):
    result = await handler.handle_request("Second Happy Time")
    assert result.title == "Second Happy Time"
    assert "Second Happy Time" in result.html
    assert result.url == "https://en.wikipedia.org/wiki/Second_Happy_Time"


async def test_found_via_redirect_reports_real_title(handler):
    result = await handler.handle_request("Operation_Drumbeat")
    assert result.title == "Second Happy Time"


async def test_unknown_title_is_404(handler):
    with pytest.raises(HTTPException) as caught:
        await handler.handle_request("No such battle")
    assert caught.value.status_code == 404
    assert caught.value.detail == "Geen artikel voor deze veldslag."


@pytest.mark.parametrize("title", TITLES[1:])
async def test_title_with_special_characters(handler, title):
    result = await handler.handle_request(quote(title))
    assert result.title == title


async def test_second_request_is_served_from_cache(handler, monkeypatch):
    calls = []
    real = article_service.render_article

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(article_service, "render_article", counting)
    first = await handler.handle_request("Second Happy Time")
    second = await handler.handle_request("Operation Drumbeat")
    assert first == second
    assert len(calls) == 1


async def test_a_foreign_article_is_found_by_language(tmp_path):
    from app.services.storage.models import ForeignBattleArticle

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/foreign.db")
    await init_models(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(ForeignBattleArticle(lang="nl", title="Slag om K", battle="Slag om K",
                                         wikitext="De '''Slag om K''' bij [[Kornwerderzand]].",
                                         dump_name="d", extracted_at=datetime.now(timezone.utc)))
        session.add(BattleArticle(title="Slag om K", wikitext="English text.", dump_name="d",
                                  extracted_at=datetime.now(timezone.utc)))
        await session.commit()
    handler = RequestHandler(ArticleService(factory))
    result = await handler.handle_request("Slag om K", lang="nl")
    assert result.url == "https://nl.wikipedia.org/wiki/Slag_om_K"
    assert "https://nl.wikipedia.org/wiki/Kornwerderzand" in result.html
    english = await handler.handle_request("Slag om K")
    assert "English text" in english.html
    with pytest.raises(HTTPException):
        await handler.handle_request("Slag om K", lang="xx")
    await engine.dispose()

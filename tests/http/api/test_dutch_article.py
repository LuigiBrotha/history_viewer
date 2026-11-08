from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.http.api.battles.article import RequestHandler
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import BattleArticle, DutchArticle, ForeignBattleArticle
from app.services.wiki.article_service import ArticleService

NOW = datetime.now(timezone.utc)


class FakeModels:
    def __init__(self):
        self.calls = []

    def can_reach_dutch(self, lang):
        return lang in ("en", "ru")

    def to_dutch(self, lang, texts):
        self.calls.append((lang, list(texts)))
        return [f"NL[{t}]" for t in texts]


@pytest.fixture
async def setup(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(BattleArticle(title="Battle of Kursk", wikitext="The battle was fought.", dump_name="d",
                                  extracted_at=NOW))
        session.add(BattleArticle(title="Battle of Arnhem", wikitext="Fought near the bridge.", dump_name="d",
                                  extracted_at=NOW))
        session.add(DutchArticle(lang="en", title="Battle of Arnhem", kind="wikipedia", nl_title="Slag om Arnhem",
                                 content="De '''Slag om Arnhem''' werd uitgevochten.", made_at=NOW))
        for lang, title in (("ru", "Курская битва"), ("be", "Бітва"), ("nl", "Slag om de Grebbeberg")):
            session.add(ForeignBattleArticle(lang=lang, title=title, battle=title, wikitext="Text.", dump_name="d",
                                             extracted_at=NOW))
        await session.commit()
    models = FakeModels()
    yield RequestHandler(ArticleService(factory, models)), models, factory
    await engine.dispose()


async def test_an_article_without_a_dutch_one_is_translated_once_and_kept(setup):
    handler, models, factory = setup
    first = await handler.handle_request("Battle of Kursk", versie="nl")
    assert first.source == "vertaald" and first.from_lang == "en"
    assert "NL[The battle was fought.]" in first.html
    assert first.url == "https://en.wikipedia.org/wiki/Battle_of_Kursk"
    again = await handler.handle_request("Battle of Kursk", versie="nl")
    assert again.html == first.html
    assert len(models.calls) == 1
    async with factory() as session:
        stored = await session.get(DutchArticle, ("en", "Battle of Kursk"))
    assert stored.kind == "vertaald" and "NL[" in stored.content


async def test_the_dutch_wikipedia_article_comes_first(setup):
    handler, models, _ = setup
    article = await handler.handle_request("Battle of Arnhem", versie="nl")
    assert article.source == "wikipedia"
    assert article.title == "Slag om Arnhem"
    assert article.url == "https://nl.wikipedia.org/wiki/Slag_om_Arnhem"
    assert "werd uitgevochten" in article.html
    assert models.calls == []


async def test_another_language_is_translated_too_and_a_language_without_a_model_is_404(setup):
    handler, models, _ = setup
    article = await handler.handle_request("Курская битва", lang="ru", versie="nl")
    assert article.source == "vertaald" and article.from_lang == "ru"
    assert models.calls[0][0] == "ru"
    with pytest.raises(HTTPException) as caught:
        await handler.handle_request("Бітва", lang="be", versie="nl")
    assert caught.value.status_code == 404
    assert caught.value.detail == "Geen Nederlandse versie voor dit artikel."


async def test_the_original_says_whether_a_dutch_version_can_be_had(setup):
    handler, _, _ = setup
    assert (await handler.handle_request("Battle of Kursk")).dutch is True
    assert (await handler.handle_request("Battle of Arnhem")).source == "origineel"
    assert (await handler.handle_request("Бітва", lang="be")).dutch is False
    assert (await handler.handle_request("Slag om de Grebbeberg", lang="nl")).dutch is False

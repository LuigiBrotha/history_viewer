import bz2
import gzip
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import Base, DutchArticle, ForeignBattleArticle
from tools.dutch_articles import dutch_counterparts, find_dutch, originals


def test_dutch_counterparts_maps_each_original_to_the_dutch_page_linking_to_it():
    lines = ["INSERT INTO `langlinks` VALUES (10,'en','Battle of Arnhem'),(11,'ru','Курская_битва'),(12,'en','Other');"]
    wanted = {("en", "Battle of Arnhem"), ("ru", "Курская битва")}
    assert dutch_counterparts(lines, wanted) == {("en", "Battle of Arnhem"): 10, ("ru", "Курская битва"): 11}


def test_dutch_battles_need_no_dutch_version():
    assert originals([{"title": "A"}, {"title": "B", "lang": "nl"}, {"title": "C", "lang": "ru"}]) == [
        ("en", "A"), ("ru", "C")]


def test_find_dutch_uses_scanned_articles_and_fetches_the_others(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        session.add(ForeignBattleArticle(lang="nl", title="Slag om de Schelde", battle="Battle of the Scheldt",
                                         wikitext="Schelde.", dump_name="d", extracted_at=datetime.now(timezone.utc)))
    with gzip.open(tmp_path / "nlwiki-1-langlinks.sql.gz", "wt", encoding="utf-8") as out:
        out.write("INSERT INTO `langlinks` VALUES (7,'en','Battle of Arnhem');\n")
    with bz2.open(tmp_path / "nlwiki-1-pages-articles-multistream-index.txt.bz2", "wt", encoding="utf-8") as out:
        out.write("100:7:Slag om Arnhem\n")
    asked = []

    def fetch(params, url):
        asked.append((params["titles"], url))
        return {"query": {"pages": [{"title": "Slag om Arnhem", "revisions": [{"slots": {"main": {"content": "Arnhem."}}}]}]}}

    battles = [{"title": "Battle of the Scheldt"}, {"title": "Battle of Arnhem"}, {"title": "Battle of Kursk"}]
    assert find_dutch(battles, url, tmp_path, fetch) == 2
    assert asked == [("Slag om Arnhem", "https://nl.wikipedia.org/w/api.php")]
    with Session(engine) as session:
        rows = {(r.title, r.nl_title, r.content) for r in session.scalars(select(DutchArticle))}
    assert rows == {("Battle of the Scheldt", "Slag om de Schelde", "Schelde."), ("Battle of Arnhem", "Slag om Arnhem", "Arnhem.")}
    engine.dispose()

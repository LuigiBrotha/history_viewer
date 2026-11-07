import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.storage.models import Base, BattleArticle, ForeignBattleArticle
from tools.enrich_battles import run

EN = "{{Infobox military conflict\n| combatant1 = {{flag|United Kingdom}}\n| combatant2 = {{flagcountry|Nazi Germany}}\n}}"
NL = "{{Infobox militair conflict\n| combatant1=[[Nederland]]\n| combatant2=[[nazi-Duitsland]]\n}}"
DE = "{{Infobox Militärischer Konflikt\n|KONTRAHENT1={{POL-1928}}\n|KONTRAHENT2={{DEU-1935}}<br />{{SUN-1923}}\n}}"


def setup(tmp_path, battles):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session, session.begin():
        session.add(BattleArticle(title="Battle A", wikitext=EN, dump_name="d", extracted_at=now))
        session.add(BattleArticle(title="Battle B", wikitext="No infobox.", dump_name="d", extracted_at=now))
        session.add(ForeignBattleArticle(lang="nl", title="Slag om B", battle="Battle B", wikitext=NL, dump_name="d",
                                         extracted_at=now))
        session.add(ForeignBattleArticle(lang="de", title="Schlacht C", battle="Schlacht C", wikitext=DE, dump_name="d",
                                         extracted_at=now))
    engine.dispose()
    path = tmp_path / "battles.json"
    path.write_text(json.dumps(battles), encoding="utf-8")
    return path, url


def test_run_adds_the_countries_of_each_battle(tmp_path):
    path, url = setup(tmp_path, [
        {"title": "Battle A", "start": "1940-01-01"},
        {"title": "Battle B", "start": "1940-05-10"},
        {"title": "Schlacht C", "start": "1939-09-01", "lang": "de"},
        {"title": "Battle D", "start": "1941-01-01"},
    ])
    run(path, url)
    battles = json.loads(path.read_text(encoding="utf-8"))
    assert [b["countries"] for b in battles] == [
        ["Verenigd Koninkrijk", "Duitsland"],
        ["Nederland", "Duitsland"],
        ["Polen", "Duitsland", "Sovjet-Unie"],
        [],
    ]
    assert [b["title"] for b in battles] == ["Battle A", "Battle B", "Schlacht C", "Battle D"]
    assert battles[0]["start"] == "1940-01-01"


def test_a_second_run_gives_the_same_file(tmp_path):
    path, url = setup(tmp_path, [{"title": "Battle A", "start": "1940-01-01"}])
    run(path, url)
    first = path.read_text(encoding="utf-8")
    run(path, url)
    assert path.read_text(encoding="utf-8") == first

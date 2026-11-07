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


from tools.enrich_battles import linked_names, people_and_units


def test_linked_names_keeps_linked_articles_only():
    field = ("{{flagicon|Nazi Germany}} [[Erwin Rommel]]<br />{{flagicon|Italy}} [[Ettore Bastico|E. Bastico]] †<br />"
             "[[File:Flag.svg|20px]] [[Nazi Germany|Germany]] Some unlinked general [[Erwin_Rommel]] [[Category:X]]")
    assert linked_names(field) == ["Erwin Rommel", "Ettore Bastico"]


def test_people_and_units_reads_each_language():
    en = ("{{Infobox military conflict\n| commander1 = [[Erwin Rommel]]\n| commander2 = [[Bernard Montgomery]]\n"
          "| units1 = [[Afrika Korps]]\n| units2 = [[Eighth Army (United Kingdom)|Eighth Army]]\n}}")
    assert people_and_units("en", en) == (["Erwin Rommel", "Bernard Montgomery"], ["Afrika Korps", "Eighth Army (United Kingdom)"])
    de = "{{Infobox Militärischer Konflikt\n|BEFEHLSHABER1=[[Eduard Dietl]]\n|BEFEHLSHABER2=[[William Whitworth]]\n}}"
    assert people_and_units("de", de) == (["Eduard Dietl", "William Whitworth"], [])
    pl = "{{Wojna infobox\n|dowódca1 = [[Tadeusz Kutrzeba]]<br>[[Władysław Bortnowski]]\n|dowódca2 = [[Gerd von Rundstedt]]\n}}"
    assert people_and_units("pl", pl)[0] == ["Tadeusz Kutrzeba", "Władysław Bortnowski", "Gerd von Rundstedt"]


def test_run_adds_commanders_and_units(tmp_path):
    path, url = setup(tmp_path, [{"title": "Battle A", "start": "1940-01-01"}])
    run(path, url)
    battle = json.loads(path.read_text(encoding="utf-8"))[0]
    assert battle["commanders"] == [] and battle["units"] == []


def test_ranks_are_dropped_and_units_in_the_commander_field_count_as_units():
    en = ("{{Infobox military conflict\n| commander1 = [[Admiral]] [[Karl Dönitz]]<br />[[Major (rank)|Maj.]] X"
          "<br />[[Kapitänleutnant]] [[Otto Kretschmer]]\n| commander2 = [[2nd Belorussian Front]]<br />[[Stavka]]"
          "<br />[[Ernst Busch (field marshal)]]\n| units1 = [[Army Group Centre]]\n}}")
    assert people_and_units("en", en) == (
        ["Karl Dönitz", "Otto Kretschmer", "Ernst Busch (field marshal)"],
        ["2nd Belorussian Front", "Stavka", "Army Group Centre"],
    )

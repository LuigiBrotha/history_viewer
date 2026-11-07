import bz2
import gzip
import json
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import create_engine, text

from tools.extract_other_languages import run

NL_BATTLE = "{{Infobox militair conflict\n| conflict=%s\n| date=%s\n| result=Duitse overwinning\n" \
            "| combatant1=[[Nederland]]\n| combatant2=[[nazi-Duitsland]]\n}}\n%s"
DE_BATTLE = "{{Infobox Militärischer Konflikt\n|KONFLIKT=%s\n|DATUM=%s\n|AUSGANG=Deutscher Sieg\n" \
            "|KONTRAHENT1={{DEU-1935}}\n|KONTRAHENT2={{GBR}}\n}}\n%s"


def dump(path, pages):
    body = "".join(
        f"<page><title>{escape(title)}</title><ns>{ns}</ns><id>{page_id}</id>"
        f"<revision><text>{escape(wikitext)}</text></revision></page>"
        for page_id, title, ns, wikitext in pages
    )
    xml = f'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">{body}</mediawiki>'
    path.write_bytes(bz2.compress(xml.encode("utf-8")))


def langlinks(path, rows):
    values = ",".join(f"({page_id},'{lang}','{title}')" for page_id, lang, title in rows)
    path.write_bytes(gzip.compress(f"INSERT INTO `langlinks` VALUES {values};\n".encode("utf-8")))


@pytest.fixture
def files(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    dump(other / "nlwiki-20261101-pages-articles-multistream.xml.bz2", [
        (1, "Slag om Arnhem", 0, NL_BATTLE % ("Slag om Arnhem", "17 september 1944", "{{Coor title dms|51|59|0|N|5|55|0|E}}")),
        (2, "Slag om Kornwerderzand", 0, NL_BATTLE % ("Slag om Kornwerderzand", "12 mei 1940", "")),
        (3, "Slag bij Waterloo", 0, NL_BATTLE % ("Waterloo", "18 juni 1815", "")),
        (4, "Overleg:Slag om Arnhem", 1, NL_BATTLE % ("x", "17 september 1944", "")),
    ])
    langlinks(other / "nlwiki-20261101-langlinks.sql.gz", [(1, "en", "Battle of Arnhem"), (1, "de", "Schlacht um Arnheim")])
    dump(other / "dewiki-20261101-pages-articles-multistream.xml.bz2", [
        (7, "Schlacht um Arnheim", 0, DE_BATTLE % ("Arnheim", "17. September 1944", "")),
        (8, "Schlacht um Kornwerderzand", 0, DE_BATTLE % ("K", "12. Mai 1940", "{{Coordinate|NS=53.07|EW=5.33}}")),
    ])
    langlinks(other / "dewiki-20261101-langlinks.sql.gz", [(8, "nl", "Slag om Kornwerderzand")])
    battles = tmp_path / "battles.json"
    battles.write_text(json.dumps([
        {"title": "Battle of Arnhem", "start": "1944-09-17", "end": "1944-09-25", "lat": None, "lng": None, "winner": []},
    ]), encoding="utf-8")
    return other, battles, f"sqlite:///{tmp_path / 'test.db'}"


def rows(database_url, sql):
    engine = create_engine(database_url)
    with engine.connect() as connection:
        result = connection.execute(text(sql)).all()
    engine.dispose()
    return result


def test_run_fills_english_battles_and_adds_new_ones(files):
    other, battles_path, database_url = files
    run(other, battles_path, database_url, languages=("nl", "de"))
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    arnhem, kornwerderzand = battles
    assert arnhem["title"] == "Battle of Arnhem"
    assert (arnhem["lat"], arnhem["lng"]) == (51.98333, 5.91667)
    assert arnhem["winner"] == ["as"]
    assert (kornwerderzand["title"], kornwerderzand["lang"]) == ("Slag om Kornwerderzand", "nl")
    assert (kornwerderzand["lat"], kornwerderzand["lng"]) == (53.07, 5.33)


def test_run_stores_the_wikitext_of_each_language(files):
    other, battles_path, database_url = files
    run(other, battles_path, database_url, languages=("nl", "de"))
    stored = rows(database_url, "SELECT lang, title, battle FROM foreign_battle_articles ORDER BY lang, title")
    assert stored == [("de", "Schlacht um Arnheim", "Battle of Arnhem"),
                      ("de", "Schlacht um Kornwerderzand", "Slag om Kornwerderzand"),
                      ("nl", "Slag om Arnhem", "Battle of Arnhem"),
                      ("nl", "Slag om Kornwerderzand", "Slag om Kornwerderzand")]


def test_a_second_run_reuses_the_scanned_battles_without_reading_the_dump(files):
    other, battles_path, database_url = files
    run(other, battles_path, database_url, languages=("nl", "de"))
    first = battles_path.read_text(encoding="utf-8")
    for dump_file in other.glob("*.xml.bz2"):
        dump_file.write_bytes(b"not a dump")
    run(other, battles_path, database_url, languages=("nl", "de"))
    assert battles_path.read_text(encoding="utf-8") == first


def test_a_language_without_its_files_is_skipped(files, capsys):
    other, battles_path, database_url = files
    run(other, battles_path, database_url, languages=("nl", "de", "pl"))
    assert "pl: no dump" in capsys.readouterr().out

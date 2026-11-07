import bz2
import gzip
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import create_engine, text

from tools.fill_battle_articles import read_pages, redirects_to, run, stream_offsets, titles_for_ids

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikipedia" / "battle_pages.json"
DUMP = "enwiki-20261001-pages-articles-multistream.xml.bz2"
INDEX = "enwiki-20261001-pages-articles-multistream-index.txt.bz2"
REDIRECTS = "enwiki-20261001-redirect.sql.gz"


@pytest.fixture(scope="module")
def pages():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def page_xml(page_id, title, wikitext, ns=0):
    return (f"  <page>\n    <title>{escape(title)}</title>\n    <ns>{ns}</ns>\n    <id>{page_id}</id>\n"
            f"    <revision><text xml:space=\"preserve\">{escape(wikitext)}</text></revision>\n  </page>\n")


def build(directory, pages, battles):
    """A two-stream multistream dump, its index, a redirect.sql.gz and a battles.json."""
    streams = [
        [(1, "Battle of Kursk", pages["Battle of Kursk"]), (2, "Plain article", "Just words.")],
        [(3, "Battle of Midway", pages["Battle of Midway"]), (4, "Talk:Battle of Midway", "talk", 1)],
    ]
    data = bz2.compress(b"<mediawiki>\n<siteinfo></siteinfo>\n")
    index = []
    for stream in streams:
        offset = len(data)
        body = "".join(page_xml(*page) for page in stream)
        data += bz2.compress(body.encode("utf-8"))
        index += [f"{offset}:{page[0]}:{page[1]}" for page in stream]
    data += bz2.compress(b"</mediawiki>\n")
    index += ["999:10:Operation Citadel", "999:11:Some's, page", "999:12:Talk:Battle of Kursk",
              "999:14:Operation &quot;Seydlitz&quot; &amp; more"]
    (directory / DUMP).write_bytes(data)
    (directory / INDEX).write_bytes(bz2.compress(("\n".join(index) + "\n").encode("utf-8")))
    sql = ("-- MySQL dump\nINSERT INTO `redirect` VALUES (10,0,'Battle_of_Kursk','',''),"
           "(11,0,'Some\\'s,_page','',''),(12,1,'Battle_of_Kursk','',''),(13,0,'Paris','','');\n")
    (directory / REDIRECTS).write_bytes(gzip.compress(sql.encode("utf-8")))
    battles_path = directory / "battles.json"
    battles_path.write_text(json.dumps(battles, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return battles_path


BATTLES = [
    {"title": "Battle of Midway", "start": "1942-06-04", "lat": 28.2, "place": "Midway"},
    {"title": "Battle of Kursk", "start": "1943-07-05", "lat": None, "place": "Kursk"},
    {"title": "Battle of Nowhere", "start": "1944-01-01", "lat": None, "place": None},
]


@pytest.fixture
def files(tmp_path, pages):
    battles_path = build(tmp_path, pages, BATTLES)
    return tmp_path, battles_path, f"sqlite:///{tmp_path / 'test.db'}"


def rows(database_url, sql):
    engine = create_engine(database_url)
    with engine.connect() as connection:
        result = connection.execute(text(sql)).all()
    engine.dispose()
    return result


def test_stream_offsets_finds_both_streams_and_only_wanted_titles(files):
    directory, _, _ = files
    offsets = stream_offsets(directory / INDEX, {"Battle of Kursk", "Battle of Midway", "Missing"})
    assert set(offsets) == {"Battle of Kursk", "Battle of Midway"}
    assert offsets["Battle of Kursk"] != offsets["Battle of Midway"]


def test_titles_for_ids(files):
    directory, _, _ = files
    assert titles_for_ids(directory / INDEX, {10, 11, 99}) == {10: "Operation Citadel", 11: "Some's, page"}


def test_read_pages_reads_a_page_in_the_second_stream(files, pages):
    directory, _, _ = files
    offset = stream_offsets(directory / INDEX, {"Battle of Midway"})["Battle of Midway"]
    read = dict(read_pages(directory / DUMP, [offset]))
    assert read["Battle of Midway"] == pages["Battle of Midway"]
    assert "Battle of Kursk" not in read


def test_index_titles_are_unescaped(files):
    directory, _, _ = files
    assert titles_for_ids(directory / INDEX, {14}) == {14: 'Operation "Seydlitz" & more'}


def test_redirects_to_reads_one_row_per_line(tmp_path):
    sql = "INSERT INTO `redirect` VALUES\n(10,0,'Battle_of_Kursk','',''),\n(13,0,'Paris',NULL,NULL);\n"
    path = tmp_path / "r.sql.gz"
    path.write_bytes(gzip.compress(sql.encode("utf-8")))
    assert redirects_to(path, {"Battle of Kursk"}) == {10: "Battle of Kursk"}


def test_redirects_to_keeps_namespace_0_rows_targeting_a_battle(files):
    directory, _, _ = files
    found = redirects_to(directory / REDIRECTS, {"Battle of Kursk", "Some's, page"})
    assert found == {10: "Battle of Kursk", 11: "Some's, page"}


def test_run_stores_articles_redirects_and_winners(files, pages, capsys):
    directory, battles_path, database_url = files
    run(directory, database_url, battles_path)

    stored = dict(rows(database_url, "SELECT title, wikitext FROM battle_articles"))
    assert stored == {t: pages[t] for t in ("Battle of Kursk", "Battle of Midway")}
    assert rows(database_url, "SELECT DISTINCT dump_name FROM battle_articles") == [(DUMP,)]
    assert dict(rows(database_url, "SELECT alias, title FROM battle_redirects")) == {
        "Operation Citadel": "Battle of Kursk"}

    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    assert [b["title"] for b in battles] == [b["title"] for b in BATTLES]
    assert [{k: v for k, v in b.items() if k != "winner"} for b in battles] == BATTLES
    assert [b["winner"] for b in battles] == [["westers"], ["sovjet"], []]
    assert "Battle of Nowhere" in capsys.readouterr().out


def test_run_removes_articles_no_longer_battles(files):
    directory, battles_path, database_url = files
    run(directory, database_url, battles_path)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO battle_articles VALUES ('Gone', 'x', 'old', '2020-01-01 00:00:00')"))
        connection.execute(text("INSERT INTO battle_redirects VALUES ('Gone alias', 'Gone')"))
    engine.dispose()
    run(directory, database_url, battles_path)
    assert ("Gone",) not in rows(database_url, "SELECT title FROM battle_articles")
    assert rows(database_url, "SELECT count(*) FROM battle_redirects") == [(1,)]


def test_rerun_gives_identical_rows_and_file(files):
    directory, battles_path, database_url = files
    run(directory, database_url, battles_path)
    first = (rows(database_url, "SELECT title, wikitext FROM battle_articles ORDER BY title"),
             rows(database_url, "SELECT * FROM battle_redirects"), battles_path.read_text(encoding="utf-8"))
    run(directory, database_url, battles_path)
    second = (rows(database_url, "SELECT title, wikitext FROM battle_articles ORDER BY title"),
              rows(database_url, "SELECT * FROM battle_redirects"), battles_path.read_text(encoding="utf-8"))
    assert first == second

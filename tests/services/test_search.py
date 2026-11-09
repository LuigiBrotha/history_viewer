import sqlite3

import pytest

from app.services.search.index import build_index, index_path, plain_text
from app.services.search.search_service import SearchService, allowed_typos, typos_between, words_of


def test_plain_text_keeps_the_words_and_drops_the_markup():
    assert plain_text("'''Slag''' om [[Kursk (stad)|Koersk]] <ref>Bron</ref> {{Infobox|plaats=Rusland}}") == "Slag om Koersk Infobox plaats Rusland"
    assert plain_text("<p>Een &amp; twee</p>") == "Een & twee"


def test_words_lose_their_case_and_accents():
    assert words_of("Bismarck, Dönitz!") == ["bismarck", "donitz"]


def test_typing_errors_are_counted():
    assert typos_between("bismark", "bismarck", 1) == 1
    assert typos_between("bismrack", "bismarck", 2) == 1
    assert typos_between("kursk", "moscow", 1) == 2
    assert [allowed_typos(word) for word in ("war", "kursk", "bismarck")] == [0, 1, 2]


def test_the_index_lies_beside_the_database():
    assert index_path("sqlite+aiosqlite:////data/uboats.db").as_posix() == "/data/search_index.db"


BATTLES = [
    {"title": "Battle of Kursk", "place": "Soviet Union"},
    {"title": "Bataille de Dieppe", "title_en": "Dieppe Raid", "lang": "fr"},
    {"title": "Noordzee", "place": None},
]


@pytest.fixture
def service(tmp_path):
    database = tmp_path / "source.db"
    source = sqlite3.connect(database)
    source.executescript("""
        CREATE TABLE battle_articles (title TEXT, wikitext TEXT);
        CREATE TABLE foreign_battle_articles (lang TEXT, title TEXT, battle TEXT, wikitext TEXT);
        CREATE TABLE dutch_articles (lang TEXT, title TEXT, content TEXT);
        CREATE TABLE boats (id INTEGER, slug TEXT, number TEXT, type TEXT, builder TEXT, fate TEXT);
        CREATE TABLE patrols (boat_id INTEGER, commander TEXT, description TEXT);
        CREATE TABLE ship_details (ship_external_id TEXT, ship_type TEXT, owner TEXT, homeport TEXT, fate TEXT,
                                   convoy TEXT, route TEXT, cargo TEXT, history TEXT, notes TEXT);
        CREATE TABLE ship_hits (ship_external_id TEXT, name TEXT, date TEXT);
    """)
    source.executemany("INSERT INTO battle_articles VALUES (?, ?)", [
        ("Battle of Kursk", "The largest tank battle, near the Bismarck salient."),
        ("Dieppe Raid", "A raid on the French coast with tanks."),
    ])
    source.execute("INSERT INTO foreign_battle_articles VALUES ('ru', 'Курская битва', 'Battle of Kursk', 'Танковое сражение')")
    source.execute("INSERT INTO foreign_battle_articles VALUES ('fr', 'Bataille de Dieppe', 'Dieppe Raid', 'Un raid')")
    source.execute("INSERT INTO dutch_articles VALUES ('en', 'Dieppe Raid', '<p>Een aanval met landingsvaartuigen.</p>')")
    source.execute("INSERT INTO battle_articles VALUES ('Noordzee', 'Bismarck hier, en Bismarck daar.')")
    source.execute("INSERT INTO boats VALUES (1, 'u99', 'U-99', 'VIIB', 'Kiel', 'Scuttled')")
    source.execute("INSERT INTO patrols VALUES (1, 'Otto Kretschmer', 'Sank the Bismarck tender')")
    source.execute("INSERT INTO ship_details VALUES ('408', NULL, NULL, NULL, NULL, NULL, NULL, 'Timber', NULL, 'Torpedoed at noon')")
    source.executemany("INSERT INTO ship_hits VALUES (?, ?, ?)", [("408", "Magog", "1940-07-05"), ("408", "Magog", "1940-08-01")])
    source.commit()
    source.close()
    output = tmp_path / "search_index.db"
    assert build_index(database, BATTLES, output) >= 7
    return SearchService(output)


async def test_a_word_in_the_text_finds_every_kind_of_onderwerp(service):
    found = await service.search("bismarck")
    assert set(found.battles) == {"Battle of Kursk", "Noordzee"}
    assert found.boats == ["u99"]
    assert found.ships == []


async def test_the_most_fitting_text_comes_first(service):
    assert (await service.search("bismarck")).battles[0] == "Noordzee"


async def test_a_typing_error_still_finds_it(service):
    assert "Noordzee" in (await service.search("bismark")).battles


async def test_other_languages_and_dutch_versions_count_for_their_veldslag(service):
    assert (await service.search("сражение")).battles == ["Battle of Kursk"]
    assert (await service.search("landingsvaartuigen")).battles == ["Bataille de Dieppe"]


async def test_a_word_still_being_typed_matches_its_start(service):
    assert (await service.search("torpe")).ships == ["408"]


async def test_every_word_of_a_query_must_be_there(service):
    assert (await service.search("tank salient")).battles == ["Battle of Kursk"]
    assert (await service.search("timber salient")).battles == []


async def test_a_short_query_finds_nothing_and_quotes_do_no_harm(service):
    assert (await service.search("ta")).available and (await service.search("ta")).battles == []
    assert (await service.search('"bismarck')).boats == ["u99"]


async def test_without_an_index_it_says_so(tmp_path):
    assert not (await SearchService(tmp_path / "none.db").search("bismarck")).available

import bz2
import html
import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

import tools.extract_battles as tools_extract
from tools.extract_battles import (
    DateSkip,
    extract_battle,
    extract_coordinates,
    find_infobox,
    parse_date,
    run,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikipedia" / "battle_pages.json"


@pytest.fixture(autouse=True)
def database_in_tmp_path(tmp_path, monkeypatch):
    """run() defaults to ./uboats.db; keep the tests away from the real one."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="module")
def pages():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "raw, start, end, precision",
    [
        ("3 September 1939 – 8 May 1945", date(1939, 9, 3), date(1945, 5, 8), "day"),
        ("5 July – 23 August 1943", date(1943, 7, 5), date(1943, 8, 23), "day"),
        ("23 August 1942 – 2 February 1943", date(1942, 8, 23), date(1943, 2, 2), "day"),
        ("7 December 1941", date(1941, 12, 7), date(1941, 12, 7), "day"),
        ("4–7 June 1942", date(1942, 6, 4), date(1942, 6, 7), "day"),
        ("June 4–7, 1942", date(1942, 6, 4), date(1942, 6, 7), "day"),
        ("4-7 June 1942", date(1942, 6, 4), date(1942, 6, 7), "day"),
        ("30 December 1941 – 5 January 1942", date(1941, 12, 30), date(1942, 1, 5), "day"),
        ("25 December – 5 January 1942", date(1941, 12, 25), date(1942, 1, 5), "day"),
        ("{{start and end dates|1941|6|22|1941|12|5}}", date(1941, 6, 22), date(1941, 12, 5), "day"),
        ("{{start and end dates|df=yes|1943|7|5|1943|8|23}}", date(1943, 7, 5), date(1943, 8, 23), "day"),
        ("{{Start and end dates|1941|6|22|1941|12|5|df=y}}", date(1941, 6, 22), date(1941, 12, 5), "day"),
        ("{{Start date|1942|6|4}}", date(1942, 6, 4), date(1942, 6, 4), "day"),
        ("{{start date and age|1942|06|7|df=y}}", date(1942, 6, 7), date(1942, 6, 7), "day"),
        ("4–{{start date and age|1942|06|7|df=y}}", date(1942, 6, 4), date(1942, 6, 7), "day"),
        ("[[German declaration of war on the Soviet Union|22 June]]{{snd}}[[Winter campaign of 1941–1942|5 December 1941]]"
         "<br>({{Age in years, months, and days|month1=06|day1=22|year1=1941|month2=12|day2=05|year2=1941}})",
         date(1941, 6, 22), date(1941, 12, 5), "day"),
        ("{{circa|5 June 1944}}<ref>some source</ref>", date(1944, 6, 5), date(1944, 6, 5), "day"),
        ("c. 5 June 1944", date(1944, 6, 5), date(1944, 6, 5), "day"),
        ("17 July 1942<ref group=\"Note\">The start is debated, with {{cite book|x}} and more", date(1942, 7, 17), date(1942, 7, 17), "day"),
        ("7&nbsp;December&nbsp;1941", date(1941, 12, 7), date(1941, 12, 7), "day"),
        ("1941-12-07", date(1941, 12, 7), date(1941, 12, 7), "day"),
        ("June 1942", date(1942, 6, 1), date(1942, 6, 30), "month"),
        ("February 1940", date(1940, 2, 1), date(1940, 2, 29), "month"),
        ("June – August 1942", date(1942, 6, 1), date(1942, 8, 31), "month"),
        ("June 1942 – February 1943", date(1942, 6, 1), date(1943, 2, 28), "month"),
        ("June – 5 August 1942", date(1942, 6, 1), date(1942, 8, 5), "month"),
    ],
)
def test_parse_date_understands_the_wikipedia_forms(raw, start, end, precision):
    parsed = parse_date(raw)
    assert (parsed.start, parsed.end, parsed.precision) == (start, end, precision)


def test_parse_date_gives_the_cleaned_source_text():
    assert parse_date("[[Foo|5 July]] – 23 August 1943<br>(7 weeks)<ref>x</ref>").text == "5 July – 23 August 1943"
    assert parse_date("{{start and end dates|df=yes|1943|7|5|1943|8|23}}").text == "5 July 1943 – 23 August 1943"


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("1942", "only a year"),
        ("1941–1945", "only a year"),
        ("{{start date|1942}}", "only a year"),
        ("", "no date"),
        ("Summer 1942", "not understood"),
        ("after 5 June 1944", "not understood"),
        ("31 June 1942", "not understood"),
        ("5 June – 3 June 1942", "not understood"),
        ("5 July 1943 – 23 August 1943 – 1944", "not understood"),
        ("ongoing", "not understood"),
        ("7 June", "not understood"),
    ],
)
def test_parse_date_refuses_to_guess(raw, reason):
    with pytest.raises(DateSkip) as error:
        parse_date(raw)
    assert error.value.reason == reason


@pytest.mark.parametrize(
    "text, expected",
    [
        ("{{coord|51.7|N|36.1|E}}", (51.7, 36.1)),
        ("{{Coord|51.7|N|36.1|E|display=inline,title}}", (51.7, 36.1)),
        ("{{coord|51.7|36.1}}", (51.7, 36.1)),
        ("{{coord|-34.5|-49.25|region:AR}}", (-34.5, -49.25)),
        ("{{coord|48|42|N|44|31|E|display=inline}}", (48 + 42 / 60, 44 + 31 / 60)),
        ("{{coord|68|25|14|N|17|33|36|E|display=it}}", (68 + 25 / 60 + 14 / 3600, 17 + 33 / 60 + 36 / 3600)),
        ("{{Coord|30|N|178|W|type:event_region:UM|display=inline,title}}", (30, -178)),
        ("{{Coord|34|S|49|W|display=inline,title}}", (-34, -49)),
        ("{{Coord|21.365|-157.950|format=dms|type:event_region:US-HI}}", (21.365, -157.95)),
        ("coordinates = {{coord|10|20|S|30|40|W}}", (-(10 + 20 / 60), -(30 + 40 / 60))),
    ],
)
def test_extract_coordinates_forms(text, expected):
    lat, lng = extract_coordinates(text)
    assert lat == pytest.approx(expected[0], abs=1e-5)
    assert lng == pytest.approx(expected[1], abs=1e-5)


@pytest.mark.parametrize(
    "text",
    [
        "no coordinate at all",
        "{{Coord|format=dms|type:event_region:FR-59|display=inline,title}}",
        "{{coord|95|N|36.1|E}}",
        "{{coord|51.7|N|200|E}}",
        "{{coord|48|75|N|44|31|E}}",
        "{{coord|91|36}}",
    ],
)
def test_extract_coordinates_gives_none_when_missing_or_out_of_range(text):
    assert extract_coordinates(text) == (None, None)


def test_extract_coordinates_takes_the_first_coord_only():
    assert extract_coordinates("{{coord|format=dms}} later {{coord|1|2}}") == (None, None)
    assert extract_coordinates("{{coord|3|4}} later {{coord|1|2}}") == (3, 4)


def test_find_infobox_reads_fields_and_ignores_earlier_templates(pages):
    fields = find_infobox(pages["Battle of Kursk"])
    assert fields["conflict"] == "Battle of Kursk"
    assert fields["date"].startswith("{{start and end dates")
    assert "Eastern Front" in fields["part_of"]
    assert find_infobox(pages["Second Happy Time"]) is None


def test_find_infobox_accepts_the_other_names_in_any_case():
    for name in ("Infobox military operation", "infobox battle", "INFOBOX MILITARY CONFLICT", "Infobox_military_conflict"):
        assert find_infobox("{{%s\n| date = 1 May 1940\n}}" % name) == {"date": "1 May 1940"}
    assert find_infobox("{{Infobox person\n| date = 1 May 1940\n}}") is None


def test_find_infobox_keeps_nested_templates_and_links_in_one_field():
    fields = find_infobox("{{Infobox battle\n| a = {{x|1|b=2}} [[L|k]]\n| c = 3\n}} {{other|d=4}}")
    assert fields == {"a": "{{x|1|b=2}} [[L|k]]", "c": "3"}


def test_extract_battle_prints_and_asserts_every_fixture_article(pages, capsys):
    results = {title: extract_battle(title, text) for title, text in pages.items()}
    for title, (battle, reason) in results.items():
        print(title, "->", reason if battle is None else battle)

    def battle_of(title):
        battle, reason = results[title]
        assert battle is not None, reason
        return battle

    kursk = battle_of("Battle of Kursk")
    assert kursk["title"] == "Battle of Kursk"
    assert kursk["url"] == "https://en.wikipedia.org/wiki/Battle_of_Kursk"
    assert (kursk["start"], kursk["end"], kursk["precision"]) == ("1943-07-05", "1943-08-23", "day")
    assert kursk["date_text"] == "5 July 1943 – 23 August 1943"
    assert (kursk["lat"], kursk["lng"]) == (51.7, 36.1)
    assert kursk["part_of"] == "the Eastern Front of World War II"
    assert kursk["place"] == "Kursk, Kursk Oblast, Russian SFSR, Soviet Union"
    assert kursk["winner"] == ["sovjet"]

    atlantic = battle_of("Battle of the Atlantic")
    assert (atlantic["start"], atlantic["end"]) == ("1939-09-03", "1945-05-08")
    assert atlantic["date_text"] == "3 September 1939 – 8 May 1945"
    assert (atlantic["lat"], atlantic["lng"]) == (None, None)
    assert atlantic["part_of"] == "the Second World War"
    assert atlantic["place"].startswith("Atlantic Ocean, Río de la Plata, North Sea")

    # The start date is followed by a long note holding templates with | and =; the end date comes after it.
    stalingrad = battle_of("Battle of Stalingrad")
    assert (stalingrad["start"], stalingrad["end"]) == ("1942-07-17", "1943-02-02")
    assert stalingrad["date_text"] == "17 July 1942 – 2 February 1943"
    assert stalingrad["part_of"] == "the Eastern Front of World War II"
    assert stalingrad["place"] == "Stalingrad, Russian SFSR, Soviet Union"
    assert (stalingrad["lat"], stalingrad["lng"]) == (None, None)

    midway = battle_of("Battle of Midway")
    assert (midway["start"], midway["end"]) == ("1942-06-04", "1942-06-07")
    assert midway["date_text"] == "4–7 June 1942"
    assert (midway["lat"], midway["lng"]) == (30, -178)
    assert midway["part_of"] == "the Pacific War and World War II"
    assert midway["place"] == "Midway Atoll"

    dunkirk = battle_of("Battle of Dunkirk")
    assert (dunkirk["start"], dunkirk["end"]) == ("1940-05-26", "1940-06-04")
    assert (dunkirk["lat"], dunkirk["lng"]) == (None, None)
    assert dunkirk["part_of"] == "the Battle of France in the Second World War"
    assert dunkirk["place"] == "Dunkirk, France"

    narvik = battle_of("Battles of Narvik")
    assert (narvik["start"], narvik["end"]) == ("1940-04-09", "1940-06-08")
    assert narvik["lat"] == pytest.approx(68.42056, abs=1e-5)
    assert narvik["lng"] == pytest.approx(17.56, abs=1e-5)
    assert narvik["part_of"] is None
    assert narvik["place"] == "Narvik"

    plate = battle_of("Battle of the River Plate")
    assert (plate["start"], plate["end"]) == ("1939-12-13", "1939-12-17")
    assert (plate["lat"], plate["lng"]) == (-34, -49)
    assert plate["place"] == "Off the River Plate, South Atlantic"

    barbarossa = battle_of("Operation Barbarossa")
    assert (barbarossa["start"], barbarossa["end"]) == ("1941-06-22", "1941-12-05")
    assert barbarossa["date_text"] == "22 June – 5 December 1941"
    assert (barbarossa["lat"], barbarossa["lng"]) == (None, None)
    assert barbarossa["place"] == "Western Soviet Union"

    convoy = battle_of("Convoy HX 79")
    assert (convoy["start"], convoy["end"]) == ("1940-10-19", "1940-10-20")
    assert convoy["part_of"] == "the Battle of the Atlantic in the Second World War"
    assert convoy["place"] == "Western Approaches"

    harbor = battle_of("Attack on Pearl Harbor")
    assert (harbor["start"], harbor["end"]) == ("1941-12-07", "1941-12-07")
    assert (harbor["lat"], harbor["lng"]) == (21.365, -157.95)
    assert harbor["place"] == "Oahu, Territory of Hawaii, United States"

    assert results["Battle of Verdun"] == (None, "outside the war period")
    assert results["Second Happy Time"] == (None, "no infobox")
    assert len([b for b, _ in results.values() if b is not None]) == 10


def test_extract_battle_takes_any_battle_during_the_war_whether_or_not_it_names_world_war_ii():
    infobox = "{{Infobox military conflict\n| date = 5 June 1943\n%s}}\n"
    assert extract_battle("A", infobox % "| part_of = [[WWII]]\n")[0] is not None
    assert extract_battle("A", infobox % "| part_of = the Chinese Civil War\n")[0] is not None
    assert extract_battle("A", infobox % "")[0] is not None


def test_extract_battle_keeps_battles_that_start_before_the_war_only_when_they_overlap():
    infobox = "{{Infobox military conflict\n| date = %s\n| part_of = World War II\n}}"
    assert extract_battle("A", infobox % "1 January 1939 – 5 June 1940")[0]["start"] == "1939-01-01"
    assert extract_battle("A", infobox % "1 January 1939 – 31 August 1939") == (None, "outside the war period")
    assert extract_battle("A", infobox % "3 September 1945") == (None, "outside the war period")
    assert extract_battle("A", infobox % "2 September 1945")[0] is not None
    assert extract_battle("A", infobox % "1 September 1939")[0] is not None


def test_extract_battle_reports_dates_it_cannot_use():
    infobox = "{{Infobox military conflict\n| date = %s\n| part_of = World War II\n}}"
    assert extract_battle("A", infobox % "1942") == (None, "date: only a year")
    assert extract_battle("A", infobox % "Summer 1942") == (None, "date: not understood")
    assert extract_battle("A", "{{Infobox battle\n| part_of = World War II\n}}") == (None, "date: no date")


def test_extract_battle_url_escapes_only_what_a_url_needs():
    infobox = "{{Infobox military conflict\n| date = 5 June 1943\n| part_of = World War II\n}}"
    assert extract_battle("Siege of Leningrad (1941–1944)", infobox)[0]["url"] == (
        "https://en.wikipedia.org/wiki/Siege_of_Leningrad_(1941%E2%80%931944)"
    )
    assert extract_battle("Convoy PQ 17?", infobox)[0]["url"].endswith("Convoy_PQ_17%3F")


PAGE = """<page><title>{title}</title><ns>{ns}</ns><id>1</id>{redirect}
<revision><id>2</id><text xml:space="preserve">{text}</text></revision></page>"""
BATTLE = (
    "{{Infobox military conflict\n| conflict = X\n| date = %s\n| part_of = [[World War II]]\n"
    "| coordinates = {{coord|10|20}}\n}}\nText"
)


def make_dump(path, pages):
    def redirect_tag(redirect):
        if not redirect:
            return ""
        target = redirect if isinstance(redirect, str) else "Elsewhere"
        return '<redirect title="%s" />' % html.escape(target, quote=True)

    body = "".join(
        PAGE.format(
            title=title,
            ns=ns,
            redirect=redirect_tag(redirect),
            text=text.replace("&", "&amp;").replace("<", "&lt;"),
        )
        for title, ns, redirect, text in pages
    )
    xml = '<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><sitename>Wikipedia</sitename></siteinfo>%s</mediawiki>' % body
    with bz2.open(path, "wb") as stream:
        stream.write(xml.encode("utf-8"))


DUMP_PAGES = [
    ("Battle B", 0, False, BATTLE % "5 June 1943"),
    ("Battle A", 0, False, BATTLE % "5 June 1943"),
    ("Early battle", 0, False, BATTLE % "1 May 1940"),
    ("Old redirect", 0, True, "#REDIRECT [[Battle A]]\n" + BATTLE % "5 June 1943"),
    ("Talk:Battle A", 1, False, BATTLE % "5 June 1943"),
    ("Plain article", 0, False, "Just words, World War II."),
    ("Verdun", 0, False, (BATTLE % "21 February – 18 December 1916").replace("[[World War II]]", "[[First World War]]")),
    ("Vague", 0, False, BATTLE % "1942"),
]


def test_run_writes_sorted_compact_json_and_counts_skips(tmp_path, capsys):
    dump = tmp_path / "dump.xml.bz2"
    out = tmp_path / "out" / "battles.json"
    make_dump(dump, DUMP_PAGES)

    run(dump, out)

    text = out.read_text(encoding="utf-8")
    assert ", " not in text and ": " not in text
    battles = json.loads(text)
    assert [(b["title"], b["start"]) for b in battles] == [
        ("Early battle", "1940-05-01"),
        ("Battle A", "1943-06-05"),
        ("Battle B", "1943-06-05"),
    ]
    assert set(battles[0]) == {"title", "url", "start", "end", "precision", "date_text", "lat", "lng", "part_of", "place", "winner"}
    assert (battles[0]["lat"], battles[0]["lng"]) == (10, 20)
    report = capsys.readouterr().out
    assert "3 battles written" in report
    assert "outside the war period: 1" in report
    assert "date: only a year: 1" in report


def test_run_accepts_a_directory_holding_the_dump(tmp_path):
    make_dump(tmp_path / "enwiki-latest-pages-articles.xml.bz2", DUMP_PAGES)
    out = tmp_path / "battles.json"
    run(tmp_path, out)
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 3


def test_candidate_pages_keep_only_pages_with_a_conflict_infobox(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    titles = [title for _, title, _, target in tools_extract.iter_candidate_pages(dump) if target is None]
    assert "Plain article" not in titles
    assert "Talk:Battle A" not in titles
    assert {"Battle A", "Battle B", "Early battle"} <= set(titles)


def test_candidate_pages_can_skip_pages_already_read(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    assert [t for _, t, _, _ in tools_extract.iter_candidate_pages(dump, skip_pages=2)][0] == "Early battle"


def test_candidate_pages_report_the_number_of_each_page(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    numbers = {t: n for n, t, _, _ in tools_extract.iter_candidate_pages(dump)}
    assert numbers["Battle B"] == 1
    assert numbers["Early battle"] == 3


def test_run_adds_to_what_the_output_already_holds(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    out = tmp_path / "battles.json"
    existing = [
        {"title": "Older", "start": "1939-09-03", "end": "1939-09-04"},
        {"title": "Battle A", "start": "1900-01-01", "end": "1900-01-01"},
    ]
    out.write_text(json.dumps(existing), encoding="utf-8")

    run(dump, out)

    battles = {b["title"]: b for b in json.loads(out.read_text(encoding="utf-8"))}
    assert "Older" in battles
    assert battles["Battle A"]["start"] == "1943-06-05"


def test_run_saves_along_the_way_and_resumes_after_a_crash(tmp_path, monkeypatch):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    out = tmp_path / "battles.json"
    real = tools_extract.iter_candidate_pages

    def crashing(path, skip_pages=0):
        for count, page in enumerate(real(path, skip_pages)):
            if count == 2:
                raise OSError("interrupted")
            yield page

    monkeypatch.setattr(tools_extract, "iter_candidate_pages", crashing)
    with pytest.raises(OSError):
        run(dump, out, save_every_seconds=0)
    assert {b["title"] for b in json.loads(out.read_text(encoding="utf-8"))} == {"Battle A", "Battle B"}

    seen = []

    def recording(path, skip_pages=0):
        seen.append(skip_pages)
        return real(path, skip_pages)

    monkeypatch.setattr(tools_extract, "iter_candidate_pages", recording)
    run(dump, out, save_every_seconds=0)

    assert seen == [2]
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 3


def test_run_leaves_no_temporary_file_and_clears_progress_when_done(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    out = tmp_path / "battles.json"

    run(dump, out, save_every_seconds=0)

    assert sorted(p.name for p in tmp_path.iterdir() if "progress" in p.name or p.suffix == ".tmp") == []


@pytest.mark.parametrize("raw, start, end", [
    ("{{start and end dates|1944|01|17|1944|05|18|df=y}} (4 months and 1 day)", date(1944, 1, 17), date(1944, 5, 18)),
    ("20 May – 1 June 1941 ({{duration in days|1941|5|20|1941|6|1}} days)", date(1941, 5, 20), date(1941, 6, 1)),
    ("5 June 1943 (night)", date(1943, 6, 5), date(1943, 6, 5)),
])
def test_parse_date_ignores_notes_in_parentheses(raw, start, end):
    parsed = parse_date(raw)
    assert (parsed.start, parsed.end) == (start, end)
    assert "(" not in parsed.text


def test_run_lists_world_war_ii_articles_it_had_to_skip(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, [
        ("Clear", 0, False, BATTLE % "5 June 1943"),
        ("Unreadable", 0, False, BATTLE % "sometime in the spring"),
        ("Ancient", 0, False, (BATTLE % "sometime in the spring").replace("[[World War II]]", "[[Punic Wars]]")),
    ])
    out = tmp_path / "battles.json"

    run(dump, out, save_every_seconds=0)

    listed = (tmp_path / "battles.skipped.txt").read_text(encoding="utf-8")
    assert "Unreadable" in listed
    assert "Ancient" not in listed
    assert "Clear" not in listed


def test_candidate_pages_yield_redirects_without_an_infobox_with_their_target(tmp_path):
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, [("Alias", 0, "Target", "#REDIRECT [[Target]]"), ("Talk:Alias", 1, "Target", "x"),
                     ("Plain", 0, False, "words")])
    assert [(t, target) for _, t, _, target in tools_extract.iter_candidate_pages(dump)] == [("Alias", "Target")]


def article_dump(path, pages):
    make_dump(path, [
        ("Operation Citadel", 0, "Battle of Kursk", "#REDIRECT [[Battle of Kursk]]"),
        ("Battle of Kursk", 0, False, pages["Battle of Kursk"]),
        ("Plain article", 0, False, "Just words."),
        ("Battle of Midway", 0, False, pages["Battle of Midway"]),
        ("Midway", 0, "Battle of Midway", "#REDIRECT [[Battle of Midway]]"),
        ("Some redirect", 0, "Paris", "#REDIRECT [[Paris]]"),
    ])


def rows(database, sql):
    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        result = connection.execute(text(sql)).all()
    engine.dispose()
    return result


def run_articles(tmp_path, pages):
    dump = tmp_path / "d.xml.bz2"
    article_dump(dump, pages)
    database = tmp_path / "test.db"
    run(dump, tmp_path / "battles.json", database_url=f"sqlite:///{database}")
    return database


def test_run_stores_wikitext_of_each_battle(tmp_path, pages):
    database = run_articles(tmp_path, pages)
    stored = dict(rows(database, "SELECT title, wikitext FROM battle_articles"))
    assert stored == {t: pages[t] for t in ("Battle of Kursk", "Battle of Midway")}


def test_run_keeps_redirects_to_battles_before_and_after_target(tmp_path, pages):
    database = run_articles(tmp_path, pages)
    assert dict(rows(database, "SELECT alias, title FROM battle_redirects")) == {
        "Operation Citadel": "Battle of Kursk",
        "Midway": "Battle of Midway",
    }


def test_run_deletes_the_redirect_scratch_file_and_leaves_no_scratch_table(tmp_path, pages):
    database = run_articles(tmp_path, pages)
    assert not list(tmp_path.glob("*.redirects.sqlite"))
    assert rows(database, "SELECT name FROM sqlite_master WHERE name = 'battle_redirects_scratch'") == []


def test_rerun_replaces_rows(tmp_path, pages):
    database = run_articles(tmp_path, pages)
    run_articles(tmp_path, pages)
    assert rows(database, "SELECT count(*) FROM battle_articles") == [(2,)]
    assert rows(database, "SELECT count(*) FROM battle_redirects") == [(2,)]


def test_run_removes_articles_that_are_no_longer_battles(tmp_path, pages):
    database = run_articles(tmp_path, pages)
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO battle_articles VALUES ('Gone', 'x', 'old', '2020-01-01 00:00:00')"))
        connection.execute(text("INSERT INTO battle_redirects VALUES ('Gone alias', 'Gone')"))
    engine.dispose()
    run_articles(tmp_path, pages)
    assert {t for (t,) in rows(database, "SELECT title FROM battle_articles")} == {"Battle of Kursk", "Battle of Midway"}
    assert "Gone alias" not in {a for (a,) in rows(database, "SELECT alias FROM battle_redirects")}


def test_run_resumes_redirects_and_articles_after_a_stop(tmp_path, pages, monkeypatch):
    dump = tmp_path / "d.xml.bz2"
    article_dump(dump, pages)
    database = tmp_path / "test.db"
    url = f"sqlite:///{database}"
    out = tmp_path / "battles.json"
    real = tools_extract.iter_candidate_pages

    def crashing(path, skip_pages=0):
        for count, page in enumerate(real(path, skip_pages)):
            if count == 3:
                raise OSError("interrupted")
            yield page

    monkeypatch.setattr(tools_extract, "iter_candidate_pages", crashing)
    with pytest.raises(OSError):
        run(dump, out, save_every_seconds=0, database_url=url)
    assert list(tmp_path.glob("*.redirects.sqlite"))

    monkeypatch.setattr(tools_extract, "iter_candidate_pages", real)
    run(dump, out, save_every_seconds=0, database_url=url)

    assert rows(database, "SELECT count(*) FROM battle_articles") == [(2,)]
    assert dict(rows(database, "SELECT alias, title FROM battle_redirects")) == {
        "Operation Citadel": "Battle of Kursk",
        "Midway": "Battle of Midway",
    }
    assert not list(tmp_path.glob("*.redirects.sqlite"))


def test_the_database_stays_free_for_other_writers_during_a_run(tmp_path, pages, monkeypatch):
    import sqlite3

    database = tmp_path / "test.db"
    real = tools_extract.extract_battle
    seen = []

    def checking(title, wikitext):
        if seen:
            connection = sqlite3.connect(database, timeout=0)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.rollback()
            finally:
                connection.close()
        seen.append(title)
        return real(title, wikitext)

    monkeypatch.setattr(tools_extract, "extract_battle", checking)
    dump = tmp_path / "d.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    run(dump, tmp_path / "battles.json", save_every_seconds=3600, database_url=f"sqlite:///{database}")
    assert len(seen) >= 3

import bz2
import json
from datetime import date
from pathlib import Path

import pytest

from tools.extract_battles import (
    DateSkip,
    extract_battle,
    extract_coordinates,
    find_infobox,
    iter_pages,
    parse_date,
    run,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikipedia" / "battle_pages.json"


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


def test_extract_battle_requires_world_war_ii_in_a_category_or_part_of():
    infobox = "{{Infobox military conflict\n| date = 5 June 1943\n%s}}\n"
    assert extract_battle("A", infobox % "| part_of = [[WWII]]\n")[0] is not None
    assert extract_battle("A", infobox % "| campaign = the Second World War\n")[0] is not None
    assert extract_battle("A", infobox % "" + "[[Category:Battles of World War II involving X]]")[0] is not None
    assert extract_battle("A", infobox % "" + "[[Category:Battles of World War I involving X]]") == (None, "does not name World War II")
    assert extract_battle("A", infobox % "| part_of = the Cold War\n") == (None, "does not name World War II")
    # A mention in the running text is not enough.
    assert extract_battle("A", infobox % "" + "It was part of World War II.") == (None, "does not name World War II")


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
    body = "".join(
        PAGE.format(
            title=title,
            ns=ns,
            redirect='<redirect title="Elsewhere" />' if redirect else "",
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


def test_iter_pages_streams_only_articles_that_are_not_redirects(tmp_path):
    dump = tmp_path / "dump.xml.bz2"
    make_dump(dump, DUMP_PAGES)
    titles = [title for title, _ in iter_pages(dump)]
    assert titles == ["Battle B", "Battle A", "Early battle", "Plain article", "Verdun", "Vague"]
    assert dict(iter_pages(dump))["Plain article"] == "Just words, World War II."


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
    assert set(battles[0]) == {"title", "url", "start", "end", "precision", "date_text", "lat", "lng", "part_of", "place"}
    assert (battles[0]["lat"], battles[0]["lng"]) == (10, 20)
    report = capsys.readouterr().out
    assert "3 battles written" in report
    assert "1 no infobox" in report or "no infobox: 1" in report
    assert "outside the war period: 1" in report
    assert "date: only a year: 1" in report


def test_run_accepts_a_directory_holding_the_dump(tmp_path):
    make_dump(tmp_path / "enwiki-latest-pages-articles.xml.bz2", DUMP_PAGES)
    out = tmp_path / "battles.json"
    run(tmp_path, out)
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 3

import json
from pathlib import Path

import pytest

from tools.wiki_languages import LANGUAGES, ORDER, english_date, extract_other_battle, other_coordinates

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikipedia" / "other_language_pages.json"


@pytest.fixture(scope="module")
def pages():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_order_is_dutch_german_polish():
    assert ORDER == ("nl", "de", "pl")
    assert set(LANGUAGES) == set(ORDER)


@pytest.mark.parametrize(
    "lang, raw, expected",
    [
        ("nl", "17 september - 25 september 1944", "17 September - 25 September 1944"),
        ("nl", "10 mei 1940", "10 May 1940"),
        ("de", "9. April – 8. Juni 1940", "9 April – 8 June 1940"),
        ("de", "5. – 16. Juli 1943", "5 – 16 July 1943"),
        ("de", "15. Juli – 8. August 1941", "15 July – 8 August 1941"),
        ("pl", "1–7 września 1939", "1–7 September 1939"),
        ("pl", "22 czerwca 1941 – 5 grudnia 1941", "22 June 1941 – 5 December 1941"),
        ("pl", "maj 1940", "May 1940"),
    ],
)
def test_english_date(lang, raw, expected):
    assert english_date(lang, raw) == expected


@pytest.mark.parametrize(
    "lang, title, start, end, has_position",
    [
        ("nl", "Slag om Arnhem", "1944-09-17", "1944-09-25", True),
        ("nl", "Slag om Den Haag", "1940-05-10", "1940-05-10", False),
        ("nl", "Slag om de Grebbeberg", "1940-05-11", "1940-05-13", True),
        ("de", "Schlacht um Narvik", "1940-04-09", "1940-06-08", False),
        ("de", "Kesselschlacht bei Uman", "1941-07-15", "1941-08-08", False),
        ("de", "Unternehmen Zitadelle", "1943-07-05", "1943-07-16", False),
        ("pl", "Obrona Westerplatte", "1939-09-01", "1939-09-07", False),
    ],
)
def test_extract_other_battle_reads_real_articles(pages, lang, title, start, end, has_position):
    record, reason = extract_other_battle(lang, title, pages[lang][title])
    assert reason is None
    assert (record["start"], record["end"]) == (start, end)
    assert record["lang"] == lang
    assert record["title"] == title
    assert record["url"].startswith(f"https://{lang}.wikipedia.org/wiki/")
    assert (record["lat"] is not None) == has_position
    assert record["place"]


def test_arnhem_position(pages):
    record, _ = extract_other_battle("nl", "Slag om Arnhem", pages["nl"]["Slag om Arnhem"])
    assert (record["lat"], record["lng"]) == (51.98333, 5.91667)


def test_a_battle_outside_the_war_is_skipped():
    text = "{{Infobox militair conflict\n| conflict = X\n| date = 10 mei 1918\n}}"
    assert extract_other_battle("nl", "X", text) == (None, "outside the war period")


def test_no_infobox_is_skipped():
    assert extract_other_battle("de", "X", "Nur Text.") == (None, "no infobox")


@pytest.mark.parametrize(
    "lang, text, expected",
    [
        ("nl", "{{Coor title dms|51|59|0|N|5|55|0|E|type:event}}", (51.98333, 5.91667)),
        ("nl", "{{Coor dms|52|22|N|4|54|E}}", (52.36667, 4.9)),
        ("nl", "{{Coor title dec|52.37|4.89}}", (52.37, 4.89)),
        ("de", "{{Coordinate|NS=52/30/0/N|EW=13/22/0/E|type=landmark}}", (52.5, 13.36667)),
        ("de", "{{Coordinate|NS=52.5|EW=-13.4|type=landmark}}", (52.5, -13.4)),
        ("pl", "{{Wojna infobox\n|współrzędne = 54°24′26″N 18°40′05″E\n}}", (54.40722, 18.66806)),
        ("pl", "{{Wojna infobox\n|współrzędne = 52°14′S 21°0′W\n}}", (-52.23333, -21.0)),
        ("pl", "{{Wojna infobox\n|współrzędne = \n}}", (None, None)),
    ],
)
def test_other_coordinates(lang, text, expected):
    assert other_coordinates(lang, text) == expected


from tools.battle_winner import other_side_kamp, other_winner


@pytest.mark.parametrize(
    "lang, title, expected",
    [
        ("de", "Kesselschlacht bei Uman", ["as"]),
        ("de", "Schlacht um Narvik", ["as"]),
        ("de", "Unternehmen Zitadelle", ["sovjet"]),
        ("nl", "Slag om Arnhem", ["as"]),
        ("nl", "Slag om Den Haag", ["westers"]),
        ("nl", "Slag om de Grebbeberg", ["as"]),
        ("pl", "Bitwa nad Bzurą", ["as"]),
        ("pl", "Obrona Westerplatte", ["as"]),
    ],
)
def test_other_winner_of_real_articles(pages, lang, title, expected):
    from tools.extract_battles import find_infobox

    fields = find_infobox(pages[lang][title], LANGUAGES[lang].infobox)
    assert other_winner(lang, fields) == expected


@pytest.mark.parametrize(
    "lang, field, expected",
    [
        ("de", "{{DEU-1935}}<br />{{HUN-1940}}", "as"),
        ("de", "{{SUN-1923}}", "sovjet"),
        ("de", "{{GBR}}<br />{{NOR}}", "westers"),
        ("de", "[[Sowjetunion]]", "sovjet"),
        ("nl", "[[Bestand:Flag of the United Kingdom.svg|25px]] [[Verenigd Koninkrijk]]", "westers"),
        ("nl", "[[Sovjet-Unie]]", "sovjet"),
        ("pl", "{{państwo|2RP}}", "westers"),
        ("pl", "{{państwo|III Rzesza}}", "as"),
        ("pl", "{{Państwo|DEU|1935}}", "as"),
        ("pl", "{{państwo|ZSRR}}", "sovjet"),
        ("pl", "nic", None),
    ],
)
def test_other_side_kamp(lang, field, expected):
    assert other_side_kamp(lang, field) == expected


@pytest.mark.parametrize(
    "lang, result, side1, side2, expected",
    [
        ("nl", "Geallieerde overwinning", "[[Sovjet-Unie]]", "[[nazi-Duitsland]]", ["sovjet"]),
        ("nl", "Onbeslist", "[[Nederland]]", "[[nazi-Duitsland]]", ["as", "westers"]),
        ("nl", "Tactische Japanse overwinning, strategische Amerikaanse overwinning", "[[Verenigde Staten]]", "[[Japans Keizerrijk]]", ["westers"]),
        ("de", "Sieg der Alliierten", "{{GBR}}", "{{DEU-1935}}", ["westers"]),
        ("de", "Unentschieden", "{{GBR}}", "{{DEU-1935}}", ["as", "westers"]),
        ("de", "Niederlage der Wehrmacht", "{{SUN-1923}}", "{{DEU-1935}}", ["sovjet"]),
        ("pl", "zwycięstwo Armii Czerwonej", "{{państwo|ZSRR}}", "{{państwo|III Rzesza}}", ["sovjet"]),
        ("pl", "bitwa nierozstrzygnięta", "{{państwo|2RP}}", "{{państwo|III Rzesza}}", ["as", "westers"]),
        ("pl", "klęska Niemców", "{{państwo|ZSRR}}", "{{państwo|III Rzesza}}", ["sovjet"]),
        ("pl", "", "{{państwo|ZSRR}}", "{{państwo|III Rzesza}}", []),
    ],
)
def test_other_winner_rules(lang, result, side1, side2, expected):
    language = LANGUAGES[lang]
    fields = {language.result: result, language.side1: side1, language.side2: side2}
    assert other_winner(lang, fields) == expected

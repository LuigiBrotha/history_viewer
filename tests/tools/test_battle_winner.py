import json
from pathlib import Path

import pytest

from tools.battle_winner import KAMPEN, side_kamp, winner
from tools.extract_battles import find_infobox

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "wikipedia" / "battle_pages.json"


@pytest.fixture(scope="module")
def infoboxes():
    pages = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {title: find_infobox(text) or {} for title, text in pages.items()}


def test_kampen():
    assert KAMPEN == ("as", "westers", "sovjet", "overig")


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Battle of Kursk", ["sovjet"]),
        ("Battle of Midway", ["westers"]),
        ("Convoy HX 79", ["as"]),
        ("Battle of the Atlantic", ["westers"]),
        ("Attack on Pearl Harbor", ["as"]),
        ("Operation Barbarossa", ["sovjet"]),
        ("Battle of Dunkirk", []),
        ("Second Happy Time", []),
        ("Battle of Stalingrad", ["sovjet"]),
        ("Battles of Narvik", ["westers"]),
    ],
)
def test_fixture_infoboxes(infoboxes, title, expected):
    assert winner(infoboxes[title]) == expected


GERMANY = "{{flagcountry|Nazi Germany}}"
UK = "{{flag|United Kingdom}}"
USSR = "{{flag|Soviet Union|1936}}"


def fields(result, combatant1=GERMANY, combatant2=UK):
    return {"result": result, "combatant1": combatant1, "combatant2": combatant2}


def test_strategic_counts_over_tactical():
    assert winner(fields("Tactical Japanese victory, strategic Allied victory",
                         "{{flag|United States|1912}}", "{{flagcountry|Empire of Japan}}")) == ["westers"]


def test_inconclusive_gives_both_columns():
    assert winner(fields("Inconclusive")) == ["as", "westers"]


@pytest.mark.parametrize("result", ["Stalemate", "Indecisive", "Draw", "Ceasefire"])
def test_other_undecided_words(result):
    assert winner(fields(result)) == ["as", "westers"]


@pytest.mark.parametrize("result", ["See aftermath", "", "  "])
def test_unknown(result):
    assert winner(fields(result)) == []


def test_chinese_victory_is_overig():
    assert winner(fields("Chinese victory", "{{flag|Republic of China (1912–1949)}}",
                         "{{flagcountry|Empire of Japan}}")) == ["overig"]


def test_allied_takes_the_non_axis_column():
    # Battle of Berlin: only the Soviet Union against Germany.
    assert winner(fields("Allied victory", USSR, GERMANY)) == ["sovjet"]


def test_allied_without_axis_column_falls_back_to_westers():
    assert winner(fields("Allied victory", USSR, UK)) == ["westers"]


def test_axis_victory():
    assert winner(fields("Axis victory", UK, GERMANY)) == ["as"]


def test_defeat_gives_the_other_column():
    assert winner(fields("German defeat", GERMANY, USSR)) == ["sovjet"]


def test_failure_gives_the_other_column():
    assert winner(fields("Axis strategic failure", GERMANY, USSR)) == ["sovjet"]


def test_decisive_and_pyrrhic_victories():
    assert winner(fields("Decisive German victory")) == ["as"]
    assert winner(fields("Pyrrhic British victory")) == ["westers"]


def test_result_with_links_and_refs():
    assert winner(fields("[[Soviet Union|Soviet]] victory<ref>Glantz</ref>", GERMANY, USSR)) == ["sovjet"]


def test_side_kamp():
    assert side_kamp("{{ubl|{{flagcountry|Nazi Germany}}|{{flagcountry|Kingdom of Italy}}}}") == "as"
    assert side_kamp("[[French Third Republic|France]]") == "westers"
    assert side_kamp("{{flag|Nazi Germany|name=German Reich}}") == "as"
    assert side_kamp("{{Flagcountry|Kingdom of Hungary (1920–1946)}}") == "as"
    assert side_kamp("{{navy|United Kingdom}}") == "westers"
    assert side_kamp("Some unknown militia") is None
    assert side_kamp("") is None


@pytest.mark.parametrize(
    "result, combatant1, combatant2, expected",
    [
        ("{{ublist|Allied victory}}", UK, GERMANY, ["westers"]),
        ("{{ubl|Heavy damage to the city |Soviet victory in the [[Battle of Berlin]] }}", UK, GERMANY, ["sovjet"]),
        ("{{ublist|[[Nazi Germany|German]] victory}} * French tactical withdrawal", UK, GERMANY, ["as"]),
        ("{{plainlist|Thai Victory}} * Japanese-mediated armistice", GERMANY, GERMANY, ["as"]),
        ("British-Norwegian victory", UK, GERMANY, ["westers"]),
        ("Polish-Soviet victory", GERMANY, USSR, ["westers"]),
        ("German withdrawal", GERMANY, USSR, ["sovjet"]),
        ("German retreat", GERMANY, USSR, ["sovjet"]),
        ("German surrender", GERMANY, UK, ["westers"]),
        ("Czech victory", GERMANY, "", ["westers"]),
        ("{{ublist|Viet Minh victory}}", "", "", ["overig"]),
    ],
)
def test_real_result_shapes(result, combatant1, combatant2, expected):
    assert winner(fields(result, combatant1, combatant2)) == expected


def test_flag_codes_colonies_and_puppet_states():
    assert side_kamp("{{flagicon|Free French}} [[French Resistance]]") == "westers"
    assert side_kamp("{{flag|UK}}") == "westers"
    assert side_kamp("{{flagicon|Gold Coast}}") == "westers"
    assert side_kamp("{{flag|Second Philippine Republic}}") == "as"
    assert side_kamp("{{flag|Democratic Federal Yugoslavia}}") == "overig"

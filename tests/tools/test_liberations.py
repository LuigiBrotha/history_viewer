import json

from tools import liberations
from tools.liberations import (
    NL_MONTHS,
    RU_MONTHS,
    lookup,
    transliterate,
    dutch_troops,
    parse_date,
    parse_nl,
    parse_ru_abroad,
    parse_ru_ussr,
)

NL = """Inleiding.
{| class="wikitable sortable"
! Datum
! Provincie
! Plaats
! Bijzonderheid
! Bevrijd door
|-
|12 september 1944
|[[Limburg (Nederlandse provincie)|Limburg]]
|[[Mesch]]
|eerste bevrijde [[Kerkdorp (nederzetting)|kerkdorp]] van Nederland
|[[30e Infanteriedivisie (Verenigde Staten)|Amerikaanse 30e Infanteriedivisie]]<ref name="a">{{Citeer web |url=x |titel=y}}</ref>
|-
|nacht van 28-29 oktober
|Noord-Brabant
|[[Sprundel]]
|
|rowspan="2"|1e Poolse Pantserdivisie<ref name="b" />
|-
|2 of 3<ref name="c" /> oktober 1944
|Limburg
|[[Rimburg (Nederland)|Rimburg]]
|
|}
"""

RU_USSR = """== Города ==
{| class="wide sortable"
|-
! Город
! Оккупирован
! Освобождён
! Войска
! Операция
|-
| rowspan="2" | [[Харьков]]
| 25 октября 1941
| 16 февраля 1943
| [[Воронежский фронт|ВорФ]]:
* [[40-я армия (СССР)|40 А]] — 5 гв. тк
| [[Харьковская операция (1943)]]
|-
| 16 марта 1943
| 23 августа 1943
|{{Скрытый
|Заголовок = соединения
|Содержание = [[Степной фронт|СтФ]]:
* [[53-я армия (СССР)|53 А]]
[[1-й Украинский фронт|1 УФ]]:
* [[5-я гвардейская армия|5 гв. А]]
}}
| [[Белгородско-Харьковская операция]]
|-bgcolor=FFDDDD
| ''Басаргино''
| 1 июля 1942
| 3 января 1943
|
|
|}
"""

RU_ABROAD = """== [[Австрия]] ==
{| class="wikitable"
|-
! Город
! Занят
|-
| [[Вена]]
| 13 апреля 1945
| [[3-й Украинский фронт|3 УФ]]:
* [[4-я гвардейская армия|4 гв. А]]
| [[Венская операция]]
|}
== [[Польша]] ==
{| class="wikitable"
|-
| [[Варшава]]
|style="background:#DAA520"| 17 января 1945
|}
== См. также ==
"""


def test_dates_take_the_last_day_and_the_year_of_the_row_above():
    assert parse_date("12 september 1944", NL_MONTHS) == "1944-09-12"
    assert parse_date("2 of 3 oktober 1944", NL_MONTHS) == "1944-10-03"
    assert parse_date("7-8 april 1945", NL_MONTHS) == "1945-04-08"
    assert parse_date("nacht van 28-29 oktober", NL_MONTHS, "1944") == "1944-10-29"
    assert parse_date("nacht van 28-29 oktober", NL_MONTHS) is None
    assert parse_date("5 июля 1941", RU_MONTHS) == "1941-07-05"
    assert parse_date("—", RU_MONTHS) is None


def test_dutch_list():
    found = parse_nl(NL)
    assert [(b.place, b.title, b.liberated, b.date_text) for b in found] == [
        ("Mesch", "Mesch", "1944-09-12", None),
        ("Sprundel", "Sprundel", "1944-10-29", "nacht van 28-29 oktober"),
        ("Rimburg", "Rimburg (Nederland)", "1944-10-03", "2 of 3 oktober 1944"),
    ]
    assert found[0].by == "Amerikaanse 30e Infanteriedivisie"
    # A rowspan carries the liberator to the row below.
    assert found[1].by == found[2].by == "1e Poolse Pantserdivisie"
    assert {b.country for b in found} == {"Nederland"}


def test_soviet_list_keeps_each_occupation_of_a_town():
    found = parse_ru_ussr(RU_USSR)
    assert [(b.place, b.occupied, b.liberated) for b in found] == [
        ("Харьков", "1941-10-25", "1943-02-16"),
        ("Харьков", "1943-03-16", "1943-08-23"),
        ("Басаргино", "1942-07-01", "1943-01-03"),
    ]
    assert found[0].by == "Voronezjfront"
    assert found[0].operation == "Харьковская операция (1943)"
    # Only the fronts, not the armies under them, from a hidden list too.
    assert found[1].by == "Steppefront, 1e Oekraïense Front"
    assert found[2].title is None and found[2].partial
    assert not found[0].partial


def test_towns_abroad_per_country():
    found = parse_ru_abroad(RU_ABROAD)
    assert [(b.place, b.country, b.verb, b.liberated) for b in found] == [
        ("Вена", "Oostenrijk", "ingenomen", "1945-04-13"),
        ("Варшава", "Polen", "bevrijd", "1945-01-17"),
    ]
    assert found[0].by == "3e Oekraïense Front"


def test_troops_in_dutch():
    assert dutch_troops("2-й Белорусский фронт") == "2e Wit-Russische Front"
    assert dutch_troops("1-й Дальневосточный фронт") == "1e Verre-Oostenfront"
    assert dutch_troops("Черноморский флот СССР во время Великой Отечественной войны") == "Zwarte Zeevloot"
    assert dutch_troops("4-я армия (СССР)") == "4-я армия"


def test_lookup_follows_redirects_and_takes_names_and_fallback_points_from_wikidata(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None):
        calls.append(params["titles"] if "titles" in params else params["ids"])
        if "wikidata" in url:
            return json.dumps({"entities": {
                "Q1": {"labels": {"nl": {"value": "Nieuw-NL"}, "en": {"value": "New"}}, "claims": {}},
                "Q2": {"labels": {"en": {"value": "Without"}}, "claims": {"P625": [
                    {"mainsnak": {"datavalue": {"value": {"latitude": 51.0, "longitude": 4.0}}}}]}},
            }})
        return json.dumps({"query": {
            "redirects": [{"from": "Oud", "to": "Nieuw"}],
            "pages": [
                {"title": "Nieuw", "coordinates": [{"lat": 52.123456, "lon": 5.1}], "pageprops": {"wikibase_item": "Q1"}},
                {"title": "Zonder", "pageprops": {"wikibase_item": "Q2"}},
                {"title": "Doorverwijs", "pageprops": {"disambiguation": "", "wikibase_item": "Q3"}},
                {"title": "Weg", "missing": True},
            ]}})

    monkeypatch.setattr(liberations, "_get", fake_get)
    monkeypatch.setattr(liberations, "PAUSE", 0)
    monkeypatch.setattr(liberations, "CACHE", tmp_path)
    result = lookup("nl", ["Oud", "Zonder", "Doorverwijs", "Weg"])
    assert result == {
        "Oud": {"lat": 52.12346, "lng": 5.1, "nl": "Nieuw-NL", "en": "New"},
        "Zonder": {"lat": 51.0, "lng": 4.0, "en": "Without"},
        "Doorverwijs": {},
        "Weg": {},
    }
    # One request for the titles, one for the Wikidata items; a rerun asks for nothing.
    assert len(calls) == 2
    assert lookup("nl", ["Oud", "Weg"]) == result
    assert len(calls) == 2


def test_transliteration_in_dutch_letters():
    assert transliterate("Жлобин") == "Zjlobin"
    assert transliterate("Харьков") == "Charkov"
    assert transliterate("Чугуев") == "Tsjoegoejev"
    assert transliterate("Елец") == "Jelets"

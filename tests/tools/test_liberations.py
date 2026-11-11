import json

from tools import liberations
from tools.liberations import (
    NL_MONTHS,
    RU_MONTHS,
    _plain_date,
    Bevrijding,
    lookup,
    transliterate,
    dutch_troops,
    drop_repeats,
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


def test_a_row_the_list_repeats_counts_once():
    havelte = dict(place="Havelte", title="Havelte", lang="nl", country="Nederland",
                   liberated="1945-04-13", source="nl")
    cadier = dict(havelte, place="Cadier", title="Cadier en Keer", liberated="1944-09-13")
    found = drop_repeats([Bevrijding(**havelte), Bevrijding(**cadier),
                          Bevrijding(**dict(cadier, place="Keer")), Bevrijding(**havelte)])
    assert [b.place for b in found] == ["Havelte", "Cadier", "Keer"]


def test_a_date_with_only_the_word_year_after_it_is_a_plain_date():
    assert _plain_date("15 февраля 1945 г.")
    assert _plain_date("15 февраля 1945 р.")
    assert _plain_date("4 марта 1945 г,")
    assert not _plain_date("2 of 3 oktober 1944")


def test_english_titles_of_operations_in_one_request(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None):
        calls.append(params["titles"])
        return json.dumps({"query": {
            "redirects": [{"from": "Берлинская операция", "to": "Берлинская наступательная операция"}],
            "pages": [
                {"title": "Берлинская наступательная операция", "langlinks": [{"lang": "en", "title": "Battle of Berlin"}]},
                {"title": "Малая операция"},
            ]}})

    monkeypatch.setattr(liberations, "_get", fake_get)
    monkeypatch.setattr(liberations, "PAUSE", 0)
    monkeypatch.setattr(liberations, "CACHE", tmp_path)
    result = liberations.english_titles("ru", ["Берлинская операция", "Малая операция"])
    assert result == {"Берлинская операция": "Battle of Berlin", "Малая операция": None}
    assert liberations.english_titles("ru", ["Малая операция"]) == result
    assert len(calls) == 1


def test_towns_sorted_by_todays_borders_get_their_wartime_country():
    from tools.liberations import wartime_country
    # German before the war: taken.
    for lat, lng in [(51.11, 17.03), (54.35, 18.65), (53.43, 14.55), (53.78, 20.49), (50.29, 18.67)]:
        assert wartime_country("Polen", lat, lng) == ("Duitsland", "ingenomen")
    # Polish between the wars: stays Polish (Warsaw, Kraków, Gdynia, Poznań, Katowice, Białystok).
    for lat, lng in [(52.23, 21.01), (50.06, 19.94), (54.52, 18.53), (52.41, 16.93), (50.26, 19.02), (53.13, 23.16)]:
        assert wartime_country("Polen", lat, lng) is None
    # Slovakia (Bratislava, Košice, Žilina) was an Axis state; Moravia (Brno, Ostrava, Zlín) occupied.
    for lat, lng in [(48.15, 17.11), (48.72, 21.26), (49.22, 18.74)]:
        assert wartime_country("Tsjechoslowakije", lat, lng) == ("Slowakije", "ingenomen")
    for lat, lng in [(49.19, 16.61), (49.83, 18.29), (49.22, 17.66)]:
        assert wartime_country("Tsjechoslowakije", lat, lng) is None


FR = """{| class="wikitable sortable alternance"
|-
! Date
! Lieu
! Dép.
! Région
! Armée(s) libératrice(s)
! Notes
|-
|align=right|{{date-|4|10|1943}} || [[Bastia]] || 2B || Corse || Française : [[Goumiers marocains|{{73e|goum}}]] || [[Libération de la Corse]]
|-
|align=right|({{date-|8|6|1944}}) || [[Tulle]] || 19 || Limousin || Française : [[maquis du Limousin]]. || Réoccupée
|-
|align=right|({{date-|8|6|1944}}) || [[Nantua]] || 01 || Rhône-Alpes || Française : maquis || Réoccupée en juillet
|-
|align=right|{{date-|16|8|1944}} || [[Tulle]] || 19 || Limousin || Française : FTP ||
|}
"""

BE = """* Op 2 september bereikten de geallieerden de Belgische zuidergrens in de provincie [[Henegouwen]]. Dezelfde dag werden [[Bergen (België)|Bergen]] en [[Doornik]] bevrijd.
* Op 4 september trokken geallieerde troepen in een overwinningsparade door de Belgische hoofdstad
* Op 4 september werd [[Antwerpen (stad)|Antwerpen]] bevrijd, evenals [[Slag om Leuven (1944)|Leuven]]<ref>x</ref>
* Op 27 oktober werd [[Meer (Antwerpen)]] bevrijd
* Op 7 september werden [[Verviers]] en de provincie [[Luxemburg (provincie)|Luxemburg]] bevrijd.
"""


def test_french_chronology_with_a_liberation_the_germans_undid():
    from tools.liberations import parse_fr
    found = parse_fr(FR)
    assert [(b.place, b.liberated, b.occupied, b.date_text) for b in found] == [
        ("Bastia", "1943-10-04", None, None),
        # Tulle was liberated for a day; the final liberation starts a new occupation the day after.
        ("Tulle", "1944-06-08", None, "tijdelijk, daarna weer bezet"),
        ("Tulle", "1944-08-16", "1944-06-09", None),
    ]
    assert found[0].by == "Frans: 73e goum"
    assert found[1].by == "Frans: maquis du Limousin"
    assert found[0].operation == "Libération de la Corse"
    assert {b.country for b in found} == {"Frankrijk"}


def test_unknown_french_units_leave_only_the_nation():
    from tools.liberations import french_liberators
    assert french_liberators("Britannique : ?") == "Brits"
    assert french_liberators("Américaine et française : ?") == "Amerikaans en Frans"


def test_france_was_occupied_in_1940_or_from_case_anton_in_1942():
    from tools.liberations import french_occupation
    # Paris, Bordeaux, Brest, Strasbourg: occupied from May 1940.
    for lat, lng in [(48.86, 2.35), (44.84, -0.58), (48.39, -4.49), (48.58, 7.75)]:
        assert french_occupation(lat, lng) == "1940-05-10"
    # Lyon, Marseille, Toulouse, Limoges, Bastia: the free zone and Corsica, from November 1942.
    for lat, lng in [(45.76, 4.84), (43.30, 5.37), (43.60, 1.44), (45.83, 1.26), (42.70, 9.45)]:
        assert french_occupation(lat, lng) == "1942-11-11"


def test_belgian_bullets_give_each_linked_place_its_day():
    from tools.liberations import parse_be
    found = parse_be(BE)
    assert [(b.place, b.title, b.liberated) for b in found] == [
        ("Bergen", "Bergen (België)", "1944-09-02"),
        ("Doornik", "Doornik", "1944-09-02"),
        ("Antwerpen", "Antwerpen (stad)", "1944-09-04"),
        ("Leuven", "Leuven", "1944-09-04"),
        ("Meer", "Meer (Antwerpen)", "1944-10-27"),
        ("Verviers", "Verviers", "1944-09-07"),
    ]
    assert {(b.country, b.occupied, b.source) for b in found} == {("België", "1940-05-10", "nl-be")}

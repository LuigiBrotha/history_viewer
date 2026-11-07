import pytest

from tools.battle_winner import KAMPEN
from tools.countries import COUNTRY_KAMP, side_countries


@pytest.mark.parametrize(
    "lang, field, expected",
    [
        ("en", "{{ubl|{{flagcountry|Nazi Germany}}|{{flagcountry|Kingdom of Italy}}}}", ["Duitsland", "Italië"]),
        ("en", "{{flag|United Kingdom}}<br />{{flag|Norway}}<br />[[French Third Republic|France]]",
         ["Verenigd Koninkrijk", "Noorwegen", "Frankrijk"]),
        ("en", "{{flag|Soviet Union|1936}} {{flag|Soviet Union}}", ["Sovjet-Unie"]),
        ("en", "{{flagicon|Free French}} [[French Resistance]]", ["Frankrijk"]),
        ("en", "[[Royal Navy]]", ["Verenigd Koninkrijk"]),
        ("de", "{{DEU-1935}}<br />{{HUN-1940}}<br />{{ROU-1881}}", ["Duitsland", "Hongarije", "Roemenië"]),
        ("de", "{{GBR}}<br />{{NOR}}<br />{{POL-1928|Ziel=Polnische Exilregierung}}", ["Verenigd Koninkrijk", "Noorwegen", "Polen"]),
        ("nl", "[[Bestand:Flag of the Netherlands.svg|25px]] [[Nederland]]", ["Nederland"]),
        ("nl", "[[Bestand:Flag of German Reich (1935–1945).svg|25px]] [[nazi-Duitsland]]", ["Duitsland"]),
        ("pl", "{{państwo|2RP}}", ["Polen"]),
        ("pl", "{{Państwo|DEU|1935}}<br>{{Państwo|Gdańsk|1920}}", ["Duitsland"]),
        ("en", "Some unknown militia", []),
        ("en", "", []),
    ],
)
def test_side_countries(lang, field, expected):
    assert side_countries(lang, field) == expected


def test_every_country_has_a_kamp():
    assert COUNTRY_KAMP
    assert set(COUNTRY_KAMP.values()) <= set(KAMPEN)
    assert COUNTRY_KAMP["Duitsland"] == "as"
    assert COUNTRY_KAMP["Polen"] == "westers"
    assert COUNTRY_KAMP["Sovjet-Unie"] == "sovjet"
    assert COUNTRY_KAMP["China"] == "overig"

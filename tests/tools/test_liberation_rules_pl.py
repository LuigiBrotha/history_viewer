from types import SimpleNamespace

from tools.liberation_articles import read_article
from tools.liberation_rules.pl import RULE as PL


def place(lat, lng):
    return SimpleNamespace(lat=lat, lng=lng, country="Polen", verb="bevrijd", occupied="1939-09-08")


def test_occupation_and_the_red_army_entering():
    text = ("Wieś została zajęta przez wojska niemieckie 8 września 1939 r. i włączona do Kraju Warty. "
            "21 stycznia 1945 r. Armia Czerwona wkroczyła do wsi.")
    assert read_article(PL, text) == ("1939-09-08", "1945-01-21")


def test_the_soviet_entry_of_1939_is_neither_occupation_nor_liberation():
    text = "17 września 1939 r. do wsi wkroczyły wojska radzieckie."
    assert read_article(PL, text) == (None, None)


def test_a_german_town_was_taken_without_occupation():
    b = PL.adjust(place(51.11, 17.03))   # Breslau
    assert (b.country, b.verb, b.occupied) == ("Duitsland", "ingenomen", None)
    b = PL.adjust(place(52.23, 21.01))   # Warsaw
    assert (b.country, b.verb, b.occupied) == ("Polen", "bevrijd", "1939-09-08")


def test_a_month_without_a_day_is_kept_apart():
    from tools.liberation_articles import read_month
    assert read_month(PL, "W styczniu 1945 r. do wsi wkroczyła Armia Czerwona.") == "1945-01"
    assert read_month(PL, "W styczniu 1945 r. otwarto szkołę.") is None


def test_a_raid_after_the_war_is_no_liberation():
    assert read_article(PL, "31 grudnia 1945 do Wołkowyi wkroczył duży oddział UPA.") == (None, None)

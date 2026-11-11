from types import SimpleNamespace

from tools.liberation_articles import read_article
from tools.liberation_rules.cs import RULE as CS


def place(lat, lng):
    return SimpleNamespace(lat=lat, lng=lng, country="Tsjechoslowakije", kamp="sovjet", verb="bevrijd",
                           occupied="1939-03-15")


def test_occupation_and_liberation_in_the_dotted_form():
    text = ("Dne 15. března 1939 byla obec obsazena německým vojskem. "
            "Obec byla osvobozena Rudou armádou 8. května 1945.")
    assert read_article(CS, text) == ("1939-03-15", "1945-05-08")


def test_a_numeric_date_stays_one_sentence_and_a_founding_date_is_no_liberation():
    assert read_article(CS, "Spolek byl založen 1. května 1945. Osvobozena byla obec až 9. 5. 1945.") == (None, "1945-05-09")
    assert read_article(CS, "Spolek byl založen 1. května 1945.") == (None, None)


def test_west_bohemia_was_freed_by_the_us_army():
    assert CS.adjust(place(49.75, 13.38)).kamp == "westers"   # Plzeň
    assert CS.adjust(place(50.08, 14.42)).kamp == "sovjet"    # Praha
    assert CS.adjust(place(49.19, 16.6)).kamp == "sovjet"     # Brno


def test_a_slovak_place_was_taken():
    b = CS.adjust(place(48.72, 21.26))   # Košice
    assert (b.country, b.verb, b.occupied) == ("Slowakije", "ingenomen", None)


def test_a_date_after_the_war_is_no_liberation():
    assert read_article(CS, "Po osvobození bylo 22. 10. 1945 obnoveno vyučování.") == (None, None)


def test_a_polish_town_with_a_czech_article_is_left_out():
    assert CS.adjust(place(50.06, 19.94)) is None   # Kraków


def test_a_month_without_a_day_is_kept_apart():
    from tools.liberation_articles import read_month
    assert read_month(CS, "Obec byla osvobozena v dubnu 1945 Rudou armádou.") == "1945-04"

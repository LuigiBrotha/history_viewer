from types import SimpleNamespace

from tools.liberation_articles import read_article
from tools.liberation_rules.sk import RULE as SK


def test_the_dotted_date_nearest_the_liberation_counts():
    text = "Dňa 29. augusta 1944 vypuklo povstanie. Obec bola oslobodená Červenou armádou 3. apríla 1945."
    assert read_article(SK, text) == (None, "1945-04-03")


def test_a_date_before_1944_is_no_liberation():
    assert read_article(SK, "Obec bola oslobodená od daní 1. mája 1943.") == (None, None)


def test_a_hungarian_or_moravian_place_is_dropped():
    place = lambda lat, lng: SimpleNamespace(lat=lat, lng=lng)
    assert SK.adjust(place(48.72, 21.26)) is not None   # Košice
    assert SK.adjust(place(47.5, 19.04)) is None        # Budapest
    assert SK.adjust(place(49.19, 16.6)) is None        # Brno


def test_a_month_without_a_day_is_kept_apart():
    from tools.liberation_articles import read_month
    assert read_month(SK, "Obec bola oslobodená v apríli 1945.") == "1945-04"


def test_a_soviet_air_raid_is_no_capture():
    text = "Obec Vyšný Hrušov bola 14. a 17. októbra 1944 bombardovaná sovietskymi leteckými silami."
    assert read_article(SK, text) == (None, None)


def test_the_germans_taking_a_town_of_the_uprising_is_no_capture():
    assert read_article(SK, "Nemecké vojská obsadili po začiatku SNP mesto 30. augusta 1944.") == (None, None)

from tools.liberation_articles import read_article
from tools.liberation_rules.nl import RULE as NL
from tools.liberations import Bevrijding


def test_a_village_liberated_on_a_date():
    text = ("In 1940 vielen de Duitsers het land binnen. "
            "Op 22 september 1944 werd het dorp door Britse troepen bevrijd, na zware gevechten.")
    assert read_article(NL, text) == (None, "1944-09-22")


def test_a_prisoner_freed_from_a_camp_is_no_liberation():
    text = ("De verzetsman werd op 5 mei 1945 bevrijd uit Dachau. "
            "Het dorp zelf werd op 14 april 1945 bevrijd door Canadezen.")
    assert read_article(NL, text) == (None, "1945-04-14")


def _place(lat, lng):
    return Bevrijding(place="X", title="X", lang="nl", country="Nederland", liberated="1944-09-10",
                      lat=lat, lng=lng, source="nl-articles")


def test_where_the_place_lies_gives_the_country():
    assert NL.adjust(_place(51.31, 3.39)).country == "Nederland"   # Sluis
    assert NL.adjust(_place(51.20, 3.81)).country == "België"      # Zelzate
    assert NL.adjust(_place(50.85, 5.69)).country == "Nederland"   # Maastricht
    assert NL.adjust(_place(51.79, 6.14)) is None                  # Kleve, Germany


def test_after_the_liberation_is_a_later_date():
    text = ("Na de bevrijding keerden zij vanaf 8 juni 1945 terug. "
            "Het dorp werd op 5 mei 1945 bevrijd.")
    assert read_article(NL, text) == (None, "1945-05-05")


def test_a_flemish_village_dates_its_occupation():
    text = "De gemeente werd rond 23 mei 1940 bezet door het Duitse leger en bevrijd op 5 september 1944."
    assert read_article(NL, text) == ("1940-05-23", "1944-09-05")
    assert NL.adjust(_place(51.226, 3.750)).country == "België"   # Assenede


def test_a_liberation_known_only_to_the_month():
    from tools.liberation_articles import read_month
    assert read_month(NL, "Het dorp werd in oktober 1944 bevrijd.") == "1944-10"

from tools.liberation_articles import read_article
from tools.liberation_rules.de import RULE as DE, soviet_side
from tools.liberations import Bevrijding


def test_a_town_taken_on_a_date_with_a_dotted_day():
    text = ("Am 1. September 1939 begann der Krieg. "
            "Am 12. April 1945 wurde der Ort kampflos von amerikanischen Truppen besetzt.")
    assert read_article(DE, text) == (None, "1945-04-12")


def test_the_date_nearest_the_verb_and_not_a_bombing():
    text = "Nach dem Luftangriff vom 3. Februar 1945 rückten am 25. April 1945 sowjetische Truppen ein."
    assert read_article(DE, text) == (None, "1945-04-25")


def test_east_of_the_meeting_line_the_red_army_took_it():
    assert soviet_side(52.52, 13.40)        # Berlin
    assert soviet_side(51.05, 13.74)        # Dresden
    assert not soviet_side(51.34, 12.37)    # Leipzig, US Army
    assert not soviet_side(52.13, 11.62)    # Magdeburg west of the Elbe
    assert not soviet_side(48.14, 11.58)    # München
    b = Bevrijding(place="X", title="X", lang="de", country="Duitsland", liberated="1945-04-25",
                   lat=52.52, lng=13.40, source="de-articles")
    assert DE.adjust(b).kamp == "sovjet"


def test_germany_of_1937_counts_and_alsace_danzig_and_austria_do_not():
    from tools.liberation_rules.de import german_1937
    assert german_1937(54.19, 16.17)        # Köslin, Pomerania
    assert german_1937(53.78, 20.49)        # Allenstein, East Prussia
    assert not german_1937(48.58, 7.75)     # Strasbourg
    assert not german_1937(54.35, 18.65)    # Danzig
    assert not german_1937(47.80, 13.04)    # Salzburg
    b = Bevrijding(place="X", title="X", lang="de", country="Duitsland", liberated="1944-11-23",
                   lat=48.58, lng=7.75, source="de-articles")
    assert DE.adjust(b) is None


def test_a_taking_known_only_to_the_month():
    from tools.liberation_articles import read_month
    assert read_month(DE, "Im April 1945 wurde das Dorf von amerikanischen Truppen besetzt.") == "1945-04"


def test_a_date_after_the_capitulation_is_no_taking():
    b = Bevrijding(place="X", title="X", lang="de", country="Duitsland", liberated="1945-09-29",
                   lat=54.0, lng=16.0, source="de-articles")
    assert DE.adjust(b) is None

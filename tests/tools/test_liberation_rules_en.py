from tools.liberation_articles import read_article
from tools.liberation_rules.en import RULE as EN, country_of
from tools.liberations import Bevrijding


def test_an_american_date_and_the_japanese_occupation():
    text = ("The town was occupied by the Japanese on December 24, 1941. "
            "It was liberated by combined Filipino and American forces on February 3, 1945.")
    assert read_article(EN, text) == ("1941-12-24", "1945-02-03")


def test_a_british_date_and_a_liberation_before_1944_is_ignored():
    text = ("The Spanish garrison was liberated on 3 May 1899. "
            "The 14th Army recaptured the town on the 3rd of May 1945.")
    assert read_article(EN, text) == (None, "1945-05-03")


def test_the_country_follows_from_where_the_place_lies():
    assert country_of(14.6, 121.0) == "Filipijnen"
    assert country_of(21.97, 96.08) == "Birma"
    assert country_of(-1.27, 116.83) == "Nederlands-Indië"
    assert country_of(13.75, 100.5) is None    # Bangkok: Thailand was Japan's ally
    assert country_of(37.56, 126.97) is None   # Seoul


def test_manchuria_was_the_red_armys_and_china_keeps_no_1941_occupation():
    b = Bevrijding(place="X", title="X", lang="en", country="Filipijnen", liberated="1945-08-20",
                   occupied="1941-12-08", lat=45.75, lng=126.65, source="en-articles")
    b = EN.adjust(b)
    assert (b.country, b.kamp, b.occupied) == ("China", "sovjet", None)


def test_pearl_harbor_is_no_occupation_of_a_town():
    b = Bevrijding(place="Naga", title="Naga", lang="en", country="Filipijnen", liberated="1945-04-13",
                   occupied="1941-12-07", lat=13.62, lng=123.19, source="en-articles")
    assert EN.adjust(b).occupied is None


def test_the_commonwealth_army_boilerplate_holds_no_liberation():
    text = ("The Philippine Constabulary were stationed in Pagadian and active from November 21, 1944, to "
            "June 30, 1946, during the liberation. The town was liberated on 10 May 1945.")
    assert read_article(EN, text) == (None, "1945-05-10")


def test_a_liberation_known_only_to_the_month():
    from tools.liberation_articles import read_month
    assert read_month(EN, "The town was liberated by American forces in February 1945.") == "1945-02"

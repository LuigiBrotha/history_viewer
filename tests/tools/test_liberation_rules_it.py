from tools.liberation_articles import read_article
from tools.liberation_rules.it import RULE as IT, adjust
from tools.liberations import Bevrijding


def place(liberated, occupied=None):
    b = Bevrijding(place="X", title="X", lang="it", country="Italië", liberated=liberated, occupied=occupied,
                   lat=44.0, lng=11.0, source="it-articles")
    b.kamp, b.verb = IT.kamp, IT.verb
    return b


def test_occupation_after_the_armistice_and_liberation_by_partisans():
    text = ("Il paese fu occupato dai tedeschi il 10 settembre 1943. "
            "Il 1º maggio 1945 il paese venne liberato dai partigiani.")
    assert read_article(IT, text) == ("1943-09-10", "1945-05-01")


def test_an_elided_article_before_the_day_still_gives_the_date():
    assert read_article(IT, "Fu liberata dagli Alleati l'8 ottobre 1943.") == (None, "1943-10-08")


def test_a_first_world_war_or_risorgimento_liberation_is_not_counted():
    text = "Fu liberata il 3 novembre 1918 dagli italiani. Nel 1944 vi fu un bombardamento."
    assert read_article(IT, text) == (None, None)


def test_a_place_taken_before_the_armistice_was_conquered_not_liberated():
    b = adjust(place("1943-07-22", occupied="1943-07-10"))
    assert (b.verb, b.occupied) == ("ingenomen", None)
    b = adjust(place("1944-09-02", occupied="1943-09-11"))
    assert (b.verb, b.occupied) == ("bevrijd", "1943-09-11")


def test_places_across_the_border_are_left_out():
    from tools.liberation_rules.it import abroad
    italian = [(45.65, 13.77), (45.94, 13.62), (43.62, 13.52), (42.46, 14.21), (41.21, 9.41), (43.79, 7.61),
               (45.79, 6.97), (35.5, 12.6), (46.5, 13.58), (38.11, 13.36)]
    foreign = [(44.87, 13.85), (45.55, 13.73), (45.96, 13.65), (43.05, 16.2), (41.92, 8.74), (43.7, 7.26),
               (45.92, 6.87), (35.9, 14.5), (46.48, 13.78)]
    assert [p for p in italian if abroad(*p)] == []
    assert [p for p in foreign if not abroad(*p)] == []


def test_a_liberation_known_only_to_the_month():
    from tools.liberation_articles import read_month
    assert read_month(IT, "Il paese fu liberato dagli Alleati nell'aprile 1945.") == "1945-04"
    assert read_month(IT, "Nel marzo 1944 il paese fu bombardato.") is None


def test_the_armistice_day_is_no_liberation_day():
    assert adjust(place("1943-09-08")) is None


def test_a_date_without_year_takes_the_year_before_it():
    text = "Il paese fu occupato il 10 settembre 1943 e liberato il 2 ottobre dagli inglesi."
    assert read_article(IT, text) == ("1943-09-10", "1943-10-02")

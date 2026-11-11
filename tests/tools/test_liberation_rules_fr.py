from tools.liberation_articles import read_article
from tools.liberation_rules.fr import RULE as FR
from tools.liberations import Bevrijding


def test_a_commune_liberated_on_a_date_in_a_template():
    text = ("Les Allemands entrent dans le village le {{date|18 juin 1940}}. "
            "Comme Metz, Rozérieulles n'est libérée qu'à l'issue de la [[bataille de Metz]], le {{date-|20 novembre 1944}}.")
    assert read_article(FR, text) == ("1940-06-18", "1944-11-20")


def test_the_first_of_the_month_and_a_released_hostage_is_no_liberation():
    text = ("Sept otages sont libérés le {{date|16 juin 1944}}. "
            "Un otage est libéré du camp le {{date|8 juillet 1944}}. "
            "Le village est libéré le {{1er}} septembre 1944 par les Américains.")
    assert read_article(FR, text) == (None, "1944-09-01")


def _place(lat, lng, liberated, occupied=None):
    return Bevrijding(place="X", title="X", lang="fr", country="Frankrijk", liberated=liberated,
                      occupied=occupied, lat=lat, lng=lng, source="fr-articles")


def test_the_occupation_defaults_to_the_demarcation_line_and_1943_counts_only_on_corsica():
    north = FR.adjust(_place(49.0, 2.3, "1944-08-25"))
    south = FR.adjust(_place(43.6, 1.4, "1944-08-19"))
    assert north.occupied == "1940-05-10"
    assert south.occupied == "1942-11-11"
    assert FR.adjust(_place(42.7, 9.45, "1943-10-04")) is not None
    assert FR.adjust(_place(48.0, 3.0, "1943-05-01")) is None


def test_a_sentence_about_a_prisoner_holds_no_date_of_the_place():
    text = ("Le dernier prisonnier libéré rentre le 9 septembre 1945. "
            "Edern est libéré le 4 août 1944.")
    assert read_article(FR, text) == (None, "1944-08-04")


def test_a_liberation_known_only_to_the_month():
    from tools.liberation_articles import read_month
    text = "La commune est libérée en septembre 1944 par les Américains."
    assert read_article(FR, text) == (None, None)
    assert read_month(FR, text) == "1944-09"

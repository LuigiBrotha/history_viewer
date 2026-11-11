from tools.liberation_articles import read_article
from tools.liberation_rules.hu import HUNGARY, RULE as HU
from tools.liberations import inside


def test_the_soviet_capture_counts_in_the_year_first_form():
    text = ("A községet [[1944]]. [[december 12.|december 12-én]] foglalták el a szovjet csapatok. "
            "1945. január 3-án iskola nyílt.")
    assert read_article(HU, text) == (None, "1944-12-12")


def test_the_german_occupation_and_the_deportations_are_no_capture():
    text = ("1944. március 19-én a német csapatok megszállták az országot. "
            "1944. május 16-án a község zsidó lakosságát deportálták, a front csak később ért ide.")
    assert read_article(HU, text) == (None, None)


def test_only_a_place_in_todays_hungary_counts():
    assert inside(HUNGARY, 47.5, 19.04)        # Budapest
    assert not inside(HUNGARY, 48.72, 21.26)   # Košice
    assert not inside(HUNGARY, 47.07, 21.93)   # Oradea

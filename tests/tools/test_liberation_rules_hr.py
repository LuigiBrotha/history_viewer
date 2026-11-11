from tools.liberation_articles import read_article
from tools.liberation_rules.hr import RULE as HR, dated


def test_a_dotted_croatian_date_gives_the_final_liberation():
    text = ("Talijani su okupirali grad 17. travnja 1941. "
            "Partizani su ga oslobodili 1942., a grad je konačno oslobođen 8. svibnja 1945. godine.")
    assert read_article(HR, text) == ("1941-04-17", "1945-05-08")


def test_a_liberation_of_1941_or_1942_is_not_the_final_one():
    assert read_article(HR, "Grad je oslobođen 4. studenoga 1942., u Bihaćkoj republici.") == (None, None)


def test_the_partisan_movement_is_no_liberation():
    text = "Narodnooslobodilački pokret 12. listopada 1944. osnovao je odbor."
    assert read_article(HR, text) == (None, None)


def test_numeric_and_roman_dates():
    months = {"listopada": 10}
    assert dated("oslobođen 20.10.1944.", months) == [(10, "1944-10-20")]
    assert dated("oslobođen 20. X. 1944.", months) == [(10, "1944-10-20")]
    assert dated("u 20.10. satu", months) == []


def test_dying_in_the_fight_for_another_city_is_no_liberation():
    text = "Poginuo je 19. listopada 1944. u borbama za oslobođenje Beograda."
    assert read_article(HR, text) == (None, None)
    assert read_article(HR, "26. listopada 1944. slavi se kao Dan oslobođenja grada.") == (None, "1944-10-26")


def test_a_liberation_known_only_to_the_month():
    from tools.liberation_articles import read_month
    assert read_month(HR, "Grad je oslobođen u travnju 1945. godine.") == "1945-04"
    assert read_month(HR, "U travnju 1941. grad su okupirali Talijani.") is None

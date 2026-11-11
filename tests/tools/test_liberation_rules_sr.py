from tools.liberation_articles import read_article
from tools.liberation_rules.sr import RULE as SR


def test_a_cyrillic_dotted_date_gives_the_liberation():
    text = "Немци су ушли у село 12. априла 1941. Село је ослобођено 14. октобра 1944. године."
    assert read_article(SR, text) == ("1941-04-12", "1944-10-14")


def test_the_uzice_republic_of_1941_is_not_the_liberation():
    assert read_article(SR, "Град је ослобођен 24. септембра 1941. године.") == (None, None)


def test_a_liberation_known_only_to_the_month():
    from tools.liberation_articles import read_month
    assert read_month(SR, "Село је ослобођено у октобру 1944. године.") == "1944-10"
    assert read_month(SR, "Партизани су га ослободили у септембру 1941.") is None

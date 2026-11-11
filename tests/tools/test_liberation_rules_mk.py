from tools.liberation_articles import read_article
from tools.liberation_rules.mk import RULE as MK


def test_a_macedonian_nominative_month_gives_the_liberation():
    text = "Бугарската војска го окупира градот на 18 април 1941. Градот е ослободен на 13 ноември 1944 година."
    assert read_article(MK, text) == ("1941-04-18", "1944-11-13")


def test_the_liberation_of_1912_is_not_counted():
    assert read_article(MK, "Селото е ослободено на 5 ноември 1912 година, во 1944 е запалено.") == (None, None)


def test_the_final_liberation_counts_not_the_first():
    text = "Градот бил ослободен на 9 септември 1944, а конечното ослободување е на 3 ноември истата година."
    assert read_article(MK, text) == (None, "1944-11-03")

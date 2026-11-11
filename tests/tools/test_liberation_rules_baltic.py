from tools.liberation_articles import read_article
from tools.liberation_rules.lt import RULE as LT
from tools.liberation_rules.lv import RULE as LV


def test_lithuanian_year_first_dates_and_the_annexation_is_no_occupation():
    text = ("1940 m. birželio 15 d. Lietuvą okupavo SSRS. "
            "1941 m. birželio 24 d. miestelį užėmė vokiečių kariuomenė. "
            "1944 m. liepos 13 d. miestelį užėmė sovietų kariuomenė.")
    assert read_article(LT, text) == ("1941-06-24", "1944-07-13")


def test_latvian_year_first_dates():
    text = ("1941. gada 1. jūlijā ciemu okupēja vācu karaspēks. "
            "1944. gada 13. oktobrī Sarkanā armija ieņēma Rīgu.")
    assert read_article(LV, text) == ("1941-07-01", "1944-10-13")


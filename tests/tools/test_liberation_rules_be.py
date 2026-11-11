from tools.liberation_articles import read_article
from tools.liberation_rules.be import RULE as BE
from tools.liberations import Bevrijding


def test_a_village_gives_its_occupation_and_liberation():
    text = ("Вёска была акупавана нацыстамі 25 жніўня 1941 г., а вызвалена ад нямецкіх акупантаў "
            "29 лістапада 1943 г. у ходзе Нараўлянскай аперацыі.")
    assert read_article(BE, text) == ("1941-08-25", "1943-11-29")


def test_the_annexation_of_1939_is_no_occupation():
    text = ("17 верасня 1939 года вёска занята Чырвонай Арміяй. "
            "Падчас Вялікай Айчыннай вайны 5 ліпеня 1944 года вызвалена ад захопнікаў.")
    assert read_article(BE, text) == (None, "1944-07-05")


def test_a_man_relieved_of_his_post_and_a_liberation_army_are_no_liberation():
    text = ("12 сакавіка 1944 года ён быў вызвалены ад пасады старшыні. "
            "1 мая 1944 года сфарміравана Руская вызваленчая армія.")
    assert read_article(BE, text) == (None, None)


def test_what_came_after_the_liberation_is_not_its_date():
    text = "Пасля вызвалення вёскі 22 сакавіка 1945 года былі забіты старшыні сельсавета."
    assert read_article(BE, text) == (None, None)


def test_a_date_after_the_summer_of_1944_is_dropped():
    late = Bevrijding(place="Кашалёва", title="Кашалёва", lang="be", country="Sovjet-Unie",
                      liberated="1945-03-22", lat=52.6, lng=24.6, source="be-articles")
    summer = Bevrijding(place="Моталь", title="Моталь", lang="be", country="Sovjet-Unie",
                        liberated="1944-07-16", lat=52.3, lng=25.6, source="be-articles")
    assert BE.adjust(late) is None
    assert BE.adjust(summer) is summer

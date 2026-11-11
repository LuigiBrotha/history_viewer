from tools.liberation_articles import already_listed, read_article
from tools.liberation_rules.uk import RULE as UK
from tools.liberations import Bevrijding

NIZHYN = """'''Ніжин''' — місто.
== Історія ==
Під час [[Німецько-радянська війна|війни]] місто було окуповане [[2 вересня]] [[1941]] року.
У 1942 році розстріляно 3000 євреїв.
[[15 вересня]] [[1943]] року&nbsp;— Ніжин звільнено від німецьких окупантів.<ref>x</ref>
У 1944 році відновлено завод.
"""


def test_an_article_gives_occupation_and_liberation_from_their_sentences():
    assert read_article(UK, NIZHYN) == ("1941-09-02", "1943-09-15")


def test_the_date_nearest_the_verb_counts():
    text = "Село засноване 1 травня 1920 року. 5 березня 1943 року бої, а 26 березня 1944 року село визволили війська."
    assert read_article(UK, text) == (None, "1944-03-26")


def test_an_article_without_a_liberation_sentence_gives_none():
    assert read_article(UK, "У 1943 році в селі відкрито школу.") == (None, None)


def test_a_place_a_list_already_has_is_left_out():
    listed = [Bevrijding(place="Ніжин", title="Ніжин", lang="ru", country="Sovjet-Unie", liberated="1943-09-15",
                         lat=51.05, lng=31.88, source="ru-ussr")]
    same = Bevrijding(place="Ніжин", title="Ніжин", lang="uk", country="Sovjet-Unie", liberated="1943-09-16",
                      lat=51.06, lng=31.89, source="uk-articles")
    elsewhere = Bevrijding(place="Носівка", title="Носівка", lang="uk", country="Sovjet-Unie", liberated="1943-09-16",
                           lat=50.93, lng=31.58, source="uk-articles")
    assert already_listed(same, listed)
    assert not already_listed(elsewhere, listed)


def test_a_soviet_annexation_is_no_occupation_and_a_table_no_sentence():
    text = ("21 вересня 1939 року село зайняли радянські війська. "
            "\n| 1 | Петро | 1944 | Загинув 10 жовтня 1944 року, звільнений з полону |\n"
            "28 липня 1944 року село звільнено від німецьких окупантів.")
    assert read_article(UK, text) == (None, "1944-07-28")


def test_a_rule_can_adjust_or_drop_each_place(monkeypatch):
    import dataclasses
    from tools import liberation_articles as la

    def adjust(b):
        if b.lng > 30:
            return None
        b.verb = "ingenomen"
        return b

    rule = dataclasses.replace(UK, adjust=adjust)
    monkeypatch.setattr(la, "search", lambda rule: ["A", "B"])
    monkeypatch.setattr(la, "texts", lambda rule, titles: {t: "5 березня 1944 року село звільнено від німецьких окупантів." for t in titles})
    monkeypatch.setattr(la, "classes", lambda lang, titles: {t: ["Q532"] for t in titles})
    monkeypatch.setattr(la.lists, "lookup", lambda lang, titles: {"A": {"lat": 49.0, "lng": 25.0}, "B": {"lat": 49.0, "lng": 35.0}})
    found = la.harvest(rule, [])
    assert [(b.title, b.verb) for b in found] == [("A", "ingenomen")]

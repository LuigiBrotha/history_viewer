from tools.liberation_articles import read_article
from tools.liberation_rules import ru
from tools.liberation_rules.ru import RULE as RU, clause_date, occupation_date
from tools.liberations import Bevrijding


def _place(title, liberated, lng=35.0, occupied=None):
    return Bevrijding(place=title, title=title, lang="ru", country="Sovjet-Unie", liberated=liberated,
                      occupied=occupied, lat=55.0, lng=lng, source="ru-articles")


def test_a_village_gives_its_occupation_and_liberation():
    text = ("2 июля 1942 года село было оккупировано немецкими войсками.\n"
            "7 февраля 1943 года Поповка была освобождена от немецких оккупантов.")
    assert read_article(RU, text) == ("1942-07-02", "1943-02-07")


def test_an_occupation_of_1941_beside_the_verb_gives_way_to_the_liberation_clause(monkeypatch):
    text = ("Занят немецко-фашистскими оккупантами 1 августа 1941 года, "
            "освобождён от оккупантов 30 января 1944 года.")
    # The nearest date to the verb is the occupation; the rule's clause reading corrects it.
    occupied, liberated = read_article(RU, text)
    monkeypatch.setattr(ru, "_lines", lambda: {"Сиверский": text})
    place = RU.adjust(_place("Сиверский", liberated, occupied=occupied))
    assert place.liberated == "1944-01-30"


def test_a_man_relieved_of_his_duties_is_no_liberation():
    text = "5 марта 1943 года освобождён от обязанностей председателя исполкома."
    assert read_article(RU, text) == (None, None)


def test_the_clause_of_the_liberation_gives_its_date():
    sentence = ("Во время Великой Отечественной войны райцентр Емельяново был оккупирован гитлеровскими "
                "войсками 12 октября 1941 года, освобожден войсками Калининского фронта 23 декабря 1941 года.")
    assert clause_date(sentence, 1941) == "1941-12-23"


def test_the_span_of_an_operation_in_brackets_is_no_liberation_date():
    sentence = ("13 марта 1944 года в ходе Березнеговато-Снигирёвской операции (6-18 марта 1944 года) "
                "Херсон был освобождён от немецко-фашистских захватчиков.")
    assert clause_date(sentence, 1941) == "1944-03-13"


def test_liberated_from_occupation_is_no_occupation():
    sentence = "Село освобождено от немецкой оккупации 23 сентября 1943 г."
    assert not occupation_date(sentence, "1943-09-23")
    trap = "14 ноября 1941 года село было оккупировано фашистскими войсками, но уже 18 декабря было освобождено."
    assert occupation_date(trap, "1941-11-14")


def test_an_early_date_that_belongs_to_the_occupation_is_dropped(monkeypatch):
    lines = {
        "Соклаково": "14 ноября 1941 года село было оккупировано фашистскими войсками, но уже 18 декабря было освобождено частями РККА.",
        "Емельяново": ("Емельяново был оккупирован гитлеровскими войсками 12 октября 1941 года, "
                       "освобожден войсками Калининского фронта 23 декабря 1941 года."),
    }
    monkeypatch.setattr(ru, "_lines", lambda: lines)
    assert RU.adjust(_place("Соклаково", "1941-11-14")) is None
    assert RU.adjust(_place("Емельяново", "1941-10-12")).liberated == "1941-12-23"


def test_a_liberation_of_1941_west_of_the_front_is_dropped(monkeypatch):
    monkeypatch.setattr(ru, "_lines", lambda: {})
    assert RU.adjust(_place("Пинск", "1941-08-01", lng=26.1)) is None
    assert RU.adjust(_place("Тихвин", "1941-12-09", lng=33.5)) is not None
    assert RU.adjust(_place("Гродно", "1944-07-16", lng=23.8)) is not None

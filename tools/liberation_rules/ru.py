"""Russian: village and town articles that say when the place was liberated ("освобождено от
немецко-фашистских захватчиков", "освобождена войсками"), beyond the towns of the ru lists."""

import json
import re
from functools import cache

from tools import liberations as lists
from tools.liberation_articles import ArticleRule, _dates, sentences
from tools.liberation_rules.be import RULE as BE
from tools.liberation_rules.uk import RULE as UK

RU_MONTHS = {m: i for i, m in enumerate(
    "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(), 1)}

PHRASE = (r"insource:/освобожд[а-яё]* (от (немецк|фашист|оккупант|гитлер|захватч|противник|врага)"
          r"|советск|красн|войск|част)/")


LIBERATED = re.compile(
    r"освобо(?:жд|д)(?!ительн)(?![а-яё]* (?:от|из) (?:должност|обязанност|плен|заключ|лагер|тюрьм|под страж))",
    re.IGNORECASE)
OCCUPIED = re.compile(r"оккупирова|оккупац|занят[аоы]?\b|захвачен|захватил|оставлен", re.IGNORECASE)


@cache
def _lines():
    path = lists.CACHE / "lines-ru.json"
    return json.loads(path.read_text()) if path.exists() else {}


# "освобождено от немецкой оккупации" names the liberation, not an occupation.
FROM_OCCUPATION = re.compile(r"от\s+(?:[а-яё-]+\s+){0,2}оккупаци[а-яё]*", re.IGNORECASE)


def _blank(sentence):
    """The sentence with "от ... оккупации" and what stands in brackets (the span of an
    operation: "(6-18 марта 1944 года)") blanked out, its positions kept."""
    sentence = re.sub(r"\([^()]*\)", lambda m: " " * len(m.group(0)), sentence)
    return FROM_OCCUPATION.sub(lambda m: " " * len(m.group(0)), sentence)


def occupation_date(sentence, iso):
    """True when the date `iso` in the sentence stands nearer an occupation than a liberation:
    "14 ноября 1941 года село было оккупировано, но уже 18 декабря освобождено" (no year)."""
    sentence = _blank(sentence)
    for at, found in _dates(sentence, RU_MONTHS):
        # "оккупирована до 3 июля 1944 года": the end of the occupation is the liberation.
        if found != iso or re.search(r"\bдо\s*$", sentence[:at]):
            continue
        free = [abs(m.start() - at) for m in LIBERATED.finditer(sentence)]
        taken = [abs(m.start() - at) for m in OCCUPIED.finditer(sentence)]
        return bool(taken) and (not free or min(taken) < min(free))
    return False


def clause_date(sentence, first_year):
    """The date in the clause of a sentence that names the liberation and no occupation:
    "оккупирован 12 октября 1941 года, освобожден войсками 23 декабря 1941 года" gives 23 December,
    though 12 October stands nearer the verb."""
    for clause in re.split(r"[,;]\s+|\s+(?:а|но)\s+", _blank(sentence)):
        verbs = [m.start() for m in LIBERATED.finditer(clause)]
        if verbs and not OCCUPIED.search(clause):
            dates = [(at, iso) for at, iso in _dates(clause, RU_MONTHS) if first_year <= int(iso[:4]) <= 1945]
            if dates:
                return min(dates, key=lambda d: min(abs(d[0] - v) for v in verbs))[1]
    return None


def _clauses(b):
    """The liberation date read clause by clause when its sentence also names the occupation;
    a liberation of 1941–1942 only on the winter counteroffensive's front (Tikhvin, Moscow, Rostov,
    Kerch: east of 30.5° E) and not when the date found belongs to the occupation."""
    for sentence in sentences(_lines().get(b.title, "")):
        if sentence.count("|") >= 3 or not LIBERATED.search(sentence):
            continue
        if b.liberated in {iso for _, iso in _dates(sentence, RU_MONTHS)}:
            better = clause_date(sentence, RULE.first_liberation)
            if better:
                b.liberated = better
            elif b.liberated < "1943-01-01" and occupation_date(sentence, b.liberated):
                return None
            break
    if b.occupied and b.occupied >= b.liberated:
        b.occupied = None
    if b.liberated < "1943-01-01" and b.lng < 30.5:
        return None
    return b


# The months without a day ("в марте 1943"): kept apart, known only to the month.
RU_MONTH_FORMS = {m: i for i, m in enumerate(
    "январе феврале марте апреле мае июне июле августе сентябре октябре ноябре декабре".split(), 1)}


RULE = ArticleRule(
    lang="ru",
    country="Sovjet-Unie",
    kamp="sovjet",
    source="ru-articles",
    queries=tuple(f"{PHRASE} {year}" for year in (1941, 1942, 1943, 1944)),
    # Not a man relieved of a post or freed from a camp, nor a "liberation" army.
    liberated=LIBERATED,
    occupied=OCCUPIED,
    months=RU_MONTHS,
    # The European USSR the Germans reached: west of the Volga, with the Crimea and the North
    # Caucasus; Belarusian and Ukrainian villages of Russian Wikipedia included.
    area=(41.0, 60.5, 20.0, 48.5),
    # The winter counteroffensive of 1941 freed Tikhvin, Rostov and the villages before Moscow.
    first_liberation=1941,
    occupation_years=(1941, 1942),
    # Russian Wikipedia has Belarusian and Ukrainian villages too: their classes count as well.
    settlements=BE.settlements | UK.settlements | {
        "Q15078955",   # urban-type settlement in Russia
        "Q27587491",   # urban-type settlement
        "Q5123999",    # city of regional significance of Ukraine
        "Q748331",     # stanitsa
        "Q2023000",    # khutor
    },
    adjust=_clauses,
    month_forms=RU_MONTH_FORMS,
)

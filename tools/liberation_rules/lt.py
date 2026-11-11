"""Lithuanian: town and village articles that say when the Red Army took the place back in 1944
("1944 m. liepos 13 d. išlaisvintas", "užėmė sovietų kariuomenė").

The Soviet return is counted as a liberation from the German occupation of June 1941; the Soviet
annexation of 1940 is no Axis occupation, so only 1941 counts as the start. Lithuanian dates put
the year first: "1944 m. liepos 13 d.".
"""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule

LT_MONTHS = {m: i for i, m in enumerate(
    "sausio vasario kovo balandžio gegužės birželio liepos rugpjūčio rugsėjo spalio lapkričio gruodžio".split(), 1)}


def lithuanian_dates(sentence, months):
    """"1944 m. liepos 13 d." (also without "m." or "d."): (position, ISO date)."""
    pattern = "|".join(months)
    found = []
    for match in re.finditer(rf"\b(19\d\d)\s*(?:m\.)?\s*({pattern})\s+(\d{{1,2}})\b", sentence.lower()):
        try:
            date = dt.date(int(match.group(1)), months[match.group(2)], int(match.group(3)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    return found


def _adjust(b):
    # South of the Neman lies the Kaliningrad oblast: East Prussia, taken, not liberated, and
    # counted by the Russian list.
    if b.lng < 22.9 and b.lat < 55.07:
        return None
    return b


RULE = ArticleRule(
    lang="lt",
    country="Sovjet-Unie",
    kamp="sovjet",
    source="lt-articles",
    queries=("užėmė 1944 kaimas", "išlaisvint 1944", "Raudonoji armija 1944 miestelis", "Raudonoji armija 1944 kaimas"),
    liberated=re.compile(r"išlaisvin|užėmė\s+(?:sovietų|raudon|tarybin)|raudonoji armija|sovietų kariuomenė", re.IGNORECASE),
    occupied=re.compile(r"okupav|okupacij|užėmė\s+(?:vokie|nacių)|vokiečių kariuomenė", re.IGNORECASE),
    months=LT_MONTHS,
    area=(53.85, 56.5, 20.9, 26.9),
    first_liberation=1944,
    occupation_years=(1941, 1941),
    dates=lithuanian_dates,
    adjust=_adjust,
)

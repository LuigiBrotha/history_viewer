"""Latvian: town and village articles that say when the Red Army took the place back in 1944–45
("1944. gada 13. oktobrī Sarkanā armija ieņēma", "atbrīvoja").

The Soviet return counts as a liberation from the German occupation of 1941 (the annexation of
1940 is no Axis occupation). Kurzeme stayed German until May 1945. Latvian dates put the year
first: "1944. gada 13. oktobrī".
"""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule

LV_MONTHS = {m: i for i, m in enumerate(
    "janvārī februārī martā aprīlī maijā jūnijā jūlijā augustā septembrī oktobrī novembrī decembrī".split(), 1)}


def latvian_dates(sentence, months):
    """"1944. gada 13. oktobrī", also "13. oktobrī" with the year after: (position, ISO date)."""
    pattern = "|".join(months)
    text = sentence.lower()
    found = []
    for match in re.finditer(rf"(?:\b(19\d\d)\.\s*gada\s+)?\b(\d{{1,2}})\.\s*({pattern})", text):
        year = match.group(1)
        if year is None:
            later = re.search(r"\b(19[34]\d)\b", text[match.end():match.end() + 40])
            year = later.group(1) if later else None
        if year is None:
            continue
        try:
            date = dt.date(int(year), months[match.group(3)], int(match.group(2)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    return found


RULE = ArticleRule(
    lang="lv",
    country="Sovjet-Unie",
    kamp="sovjet",
    source="lv-articles",
    queries=("ieņēma 1944 Sarkanā", "atbrīvoja 1944", "Sarkanā armija 1944 ciems", "Sarkanā armija 1945 ciems"),
    liberated=re.compile(r"atbrīvo|ieņēma|ienāca|sarkanā armija|padomju (?:armija|karaspēks)", re.IGNORECASE),
    occupied=re.compile(r"okupē|okupācij|vācu (?:armija|karaspēks)|vērmahts", re.IGNORECASE),
    months=LV_MONTHS,
    area=(55.6, 58.1, 20.9, 28.3),
    first_liberation=1944,
    occupation_years=(1941, 1941),
    dates=latvian_dates,
    # The Wikidata classes Latvian towns and villages carry here (cities, towns, villages).
    settlements=frozenset({"Q15584664", "Q22580836", "Q109329953", "Q15127838", "Q16355778", "Q16362394"}),
)

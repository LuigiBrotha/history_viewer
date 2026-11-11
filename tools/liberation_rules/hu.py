"""Hungarian: village and town articles that say when the Soviet troops took the place ("1944.
december 12-én a szovjet csapatok elfoglalták", "felszabadult"). Hungary was an Axis state (the
German occupation of March 1944 does not change that): its places were taken, not liberated,
and had no occupation; from Battonya, 23 September 1944, to 4 April 1945.

Hungarian Wikipedia also has an article for every village of old Hungary (Slovakia, Transylvania,
Vojvodina, Burgenland); only a place inside today's Hungary counts here."""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule
from tools.liberations import inside

HU_MONTHS = {m: i for i, m in enumerate(
    "január február március április május június július augusztus szeptember október november december".split(), 1)}

# Hungary of today, roughly (lat, lng), clockwise from Hegyeshalom.
HUNGARY = [
    (47.95, 17.10), (47.85, 17.75), (47.82, 18.80), (48.07, 18.85), (48.07, 19.30), (48.25, 19.90),
    (48.33, 20.30), (48.55, 20.55), (48.55, 21.25), (48.40, 21.70), (48.42, 22.15), (48.10, 22.90),
    (47.85, 22.75), (47.12, 21.82), (46.62, 21.45), (46.12, 20.70), (46.17, 20.05), (46.15, 19.55),
    (46.00, 19.25), (45.90, 18.90),
    (45.78, 18.40), (45.90, 17.60), (46.10, 17.20), (46.42, 16.70), (46.80, 16.30), (47.40, 16.45),
    (47.70, 16.45), (47.72, 17.05),
]

# The first Soviet troops crossed into Hungary at Battonya on 23 September 1944: an earlier date
# (the German occupation of 19 March 1944, the deportations of May–July) is no capture.
FIRST_CAPTURE = "1944-09-20"
# The last village (Nemesmedves) was taken on 12 April 1945: a later date is about something else.
LAST_CAPTURE = "1945-04-15"


def year_first_dates(sentence, months):
    """Every "1944. október 20-án" in a sentence: (position, ISO date), none before the Soviet
    troops came or after the last village was taken."""
    pattern = "|".join(months)
    found = []
    for match in re.finditer(rf"\b(19\d\d)\.?\s*({pattern})\s*(\d{{1,2}})\b", sentence.lower()):
        try:
            date = dt.date(int(match.group(1)), months[match.group(2)], int(match.group(3))).isoformat()
        except ValueError:
            continue
        if FIRST_CAPTURE <= date <= LAST_CAPTURE:
            found.append((match.start(), date))
    return found


def _in_hungary(b):
    return b if inside(HUNGARY, b.lat, b.lng) else None


RULE = ArticleRule(
    lang="hu",
    country="Hongarije",
    kamp="sovjet",
    source="hu-articles",
    queries=(
        "szovjet csapatok 1944", "szovjet csapatok 1945", "Vörös Hadsereg 1944 község",
        "Vörös Hadsereg 1945 község", "felszabadult 1944 község", "felszabadult 1945 község",
    ),
    liberated=re.compile(
        r"szovjet|Vörös Hadsereg|orosz|felszabad|elfoglal|bevonul|megszáll", re.IGNORECASE),
    occupied=None,
    months=HU_MONTHS,
    area=(45.7, 48.6, 16.1, 22.9),
    first_liberation=1944,
    verb="ingenomen",
    dates=year_first_dates,
    settlements=frozenset({
        "Q2590631",    # municipality of Hungary (község)
        "Q13218690",   # town of Hungary
    }),
    adjust=_in_hungary,
    last_liberation="1945-05-31",
)

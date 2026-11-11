"""Czech: village and town articles that say when the place was liberated ("osvobozena Rudou
armádou", "osvobozena americkou armádou").

Bohemia and Moravia were occupied on 15 March 1939, the Sudetenland annexed in October 1938; both
count as occupied from their date. The US Army freed the west of Bohemia (Plzeň, Karlovy Vary,
České Budějovice), the Red Army the rest: a place west of the demarcation line counts as western.
A Czech article of a Slovak village lies in an Axis state: taken, without occupation."""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule
from tools.liberations import inside

CS_MONTHS = {m: i for i, m in enumerate(
    "ledna února března dubna května června července srpna září října listopadu prosince".split(), 1)}
# A month without a day: "v dubnu 1945" (září is both).
CS_MONTH_FORMS = {m: i for i, m in enumerate(
    "lednu únoru březnu dubnu květnu červnu červenci srpnu září říjnu listopadu prosinci".split(), 1)}


# The war in Europe was over by the middle of May 1945: a later date (a school reopened "after the
# liberation") is about something else.
LAST_LIBERATION = "1945-05-31"


def dotted_dates(sentence, months):
    """Every "8. května 1945" or "8. 5. 1945" (Czech, Slovak) in a sentence: (position, ISO date); the year may
    follow a little later ("8. května téhož roku 1945" is rare, "8. května 1945" the rule)."""
    pattern = "|".join(months)
    found = []
    for match in re.finditer(rf"\b(\d{{1,2}})\.\s*({pattern})\b\s*(\d{{4}})?", sentence.lower()):
        year = match.group(3)
        if year is None:
            later = re.search(r"\b(19[34]\d)\b", sentence[match.end():match.end() + 40])
            year = later.group(1) if later else None
        if year is None:
            continue
        try:
            date = dt.date(int(year), months[match.group(2)], int(match.group(1)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    # And the numeric "9. 5. 1945".
    for match in re.finditer(r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(19\d\d)\b", sentence):
        try:
            date = dt.date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    return [(at, iso) for at, iso in found if iso <= LAST_LIBERATION]


# The Czech lands and Slovakia of today, roughly (lat, lng); fine enough for a village, not for one
# right on the border.
CZECH_LANDS = [
    (50.32, 12.09), (50.36, 12.47), (50.42, 12.97), (50.55, 13.25), (50.65, 13.55), (50.75, 13.95), (50.87, 14.23),
    (51.05, 14.45), (50.85, 14.83), (51.00, 15.00), (50.85, 15.25), (50.78, 15.43), (50.74, 15.74), (50.60, 16.00),
    (50.68, 16.30), (50.55, 16.50), (50.42, 16.25), (50.20, 16.55), (50.10, 16.80), (50.20, 16.85), (50.45, 17.00),
    (50.27, 17.40), (50.15, 17.65), (50.12, 17.78), (50.00, 18.10), (49.93, 18.35), (49.78, 18.62), (49.55, 18.85),
    (49.40, 18.40), (49.05, 18.00), (48.85, 17.20), (48.62, 16.95), (48.78, 16.60), (48.78, 16.05), (48.98, 15.25),
    (48.77, 14.97), (48.55, 14.35), (48.78, 13.80), (49.15, 13.20), (49.35, 12.85), (49.65, 12.45), (49.95, 12.45),
    (50.15, 12.20),
]
SLOVAKIA = [
    (49.55, 18.85), (49.60, 19.45), (49.40, 19.80), (49.18, 19.95), (49.27, 20.15), (49.40, 20.40), (49.45, 21.27),
    (49.40, 21.90), (49.00, 22.57), (48.42, 22.15), (48.40, 21.70), (48.55, 21.25), (48.55, 20.55), (48.33, 20.30),
    (48.25, 19.90), (48.07, 19.30), (48.07, 18.85), (47.78, 18.75), (47.74, 18.10), (47.95, 17.10), (48.10, 17.00),
    (48.38, 16.85), (48.62, 16.95), (48.85, 17.20), (49.05, 18.00), (49.40, 18.40),
]


def west_of_demarcation(lat, lng):
    """West of the line the US Army stopped at in May 1945, roughly Karlovy Vary – Plzeň –
    České Budějovice (the towns themselves inside): from (50.35, 13.05) to (49.0, 14.6)."""
    return lng < 13.05 + (50.35 - lat) * (14.6 - 13.05) / (50.35 - 49.0) + 0.1


def _by_place(b):
    """West Bohemia was the US Army's; a Slovak place was taken; one abroad (a Polish or Saxon
    town with a Czech article) is left to its own language."""
    if inside(CZECH_LANDS, b.lat, b.lng):
        if west_of_demarcation(b.lat, b.lng):
            b.kamp = "westers"
        return b
    if inside(SLOVAKIA, b.lat, b.lng):
        b.country, b.verb, b.occupied = "Slowakije", "ingenomen", None
        return b
    return None


RULE = ArticleRule(
    lang="cs",
    country="Tsjechoslowakije",
    kamp="sovjet",
    source="cs-articles",
    queries=(
        "osvobozena Rudou armádou 1945", "osvobozena americkou armádou 1945",
        "osvobozena 1945 obec", "osvobození obce 1945",
    ),
    # Not "sovětsk" alone: Soviet planes bombed many a village before it was freed.
    liberated=re.compile(r"osvobo|Rud[áoé] armád|americk\w* (armád|vojsk|jednot|tank)|vstoupil|obsadil", re.IGNORECASE),
    occupied=re.compile(r"okupac|okupov|obsazen|obsadil|zabrán|zábor|připojen|protektorát|německ", re.IGNORECASE),
    months=CS_MONTHS,
    # Czech Republic and Slovakia, roughly.
    area=(47.7, 51.1, 12.0, 22.6),
    first_liberation=1944,
    occupation_years=(1938, 1939),
    dates=dotted_dates,
    settlements=frozenset({
        "Q5153359",    # municipality of the Czech Republic (obec)
        "Q15978299",   # municipality with town privileges in the Czech Republic
        "Q16155707",   # městys
        "Q61089180",   # municipal part of the Czech Republic (a village within an obec)
        "Q113126851",  # self-governing city district (the former villages of Ostrava, Brno)
        "Q6784672",    # municipality of Slovakia
    }),
    adjust=_by_place,
    month_forms=CS_MONTH_FORMS,
    last_liberation="1945-05-31",
)

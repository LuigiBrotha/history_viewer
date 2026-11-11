"""Italian: comune and frazione articles that say when the place was liberated ("fu liberata dagli
Alleati il 21 aprile 1945", "liberazione ... dai partigiani").

Italy was an Axis country until the armistice of 8 September 1943; the Germans then occupied
what the Allies did not hold (8–12 September 1943). A place taken before the armistice (Sicily,
July–August 1943) was conquered, not liberated: it gets "ingenomen" and no occupation. The
liberators, Allied armies and partisans alike, count as "westers".
"""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule

IT_MONTHS = {m: i for i, m in enumerate(
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(), 1)}

ARMISTICE = "1943-09-08"


def dates(sentence, months):
    """Every day-month-year, also with an ordinal first day ("1º maggio 1945") or an elided
    article ("l'8 settembre 1943"): (position, ISO date)."""
    pattern = "|".join(months)
    found = []
    for match in re.finditer(rf"(?<!\d)(\d{{1,2}})(?:º|°|o)?\s+({pattern})\b\s*(\d{{4}})?", sentence.lower()):
        year = match.group(3)
        if year is None:
            later = re.search(r"\b(19[34]\d)\b", sentence[match.end():match.end() + 40])
            # "il 10 settembre 1943 ... e liberato il 2 ottobre": the year of the date before it.
            year = later.group(1) if later else found[-1][1][:4] if found else None
        if year is None:
            continue
        try:
            date = dt.date(int(year), months[match.group(2)], int(match.group(1)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    return found


def abroad(lat, lng):
    """True for the places in Italy's box that lie in another country: Istria and Slovenia
    (liberated by the Yugoslavs), the Dalmatian islands, Corsica, Nice and Savoy, Malta."""
    return ((lat > 45.85 and lng > 13.635) or (45.57 <= lat <= 45.85 and lng > 13.85)  # Slovenia
            or (44.5 < lat < 45.57 and lng > 13.3)                                     # Istria
            or (42.3 < lat <= 44.5 and lng > 14.4)                                     # Dalmatia
            or (41.3 < lat < 43.1 and 8.5 < lng < 9.6)                                 # Corsica
            or (lat < 44.2 and lng < 7.55) or (lat > 45.3 and lng < 6.95)              # France
            or (lat < 36.1 and lng > 14.1))                                            # Malta


def adjust(b):
    """Before the armistice Italy was the enemy: a place the Allies took then was conquered."""
    # "Dopo l'8 settembre 1943 ... località già liberate": the armistice is no liberation day.
    if abroad(b.lat, b.lng) or b.liberated == ARMISTICE:
        return None
    if b.liberated < ARMISTICE:
        b.verb = "ingenomen"
        b.occupied = None
    # The German occupation began with the armistice; an "occupation" of 1943 before it was
    # the Allies' own landing.
    if b.occupied is not None and b.occupied < ARMISTICE:
        b.occupied = None
    return b


RULE = ArticleRule(
    lang="it",
    country="Italië",
    kamp="westers",
    source="it-articles",
    queries=("insource:/liberat[ao] (dagli|dai|dalle|dal|il|l'|nel|ad opera)/ (1943 OR 1944 OR 1945)",),
    # "liberata/o/i/e", "liberazione"; not "liberale", "libero".
    liberated=re.compile(r"\bliberat[aoie]\b|\bliberazione\b|\bliberarono\b|\bliberò\b", re.IGNORECASE),
    occupied=re.compile(r"\boccupat[aoie]\b|\boccupazione\b|\boccuparono\b|\boccupò\b", re.IGNORECASE),
    months=IT_MONTHS,
    first_liberation=1943,
    occupation_years=(1943, 1943),
    # Italy within its borders of today, roughly (Sardinia and Sicily included).
    area=(35.4, 47.1, 6.6, 18.6),
    dates=dates,
    adjust=adjust,
    settlements=frozenset({
        "Q747074",    # comune of Italy
        "Q954172",    # frazione
        "Q18749720",  # Italian frazione (alternate)
        "Q15303838",  # municipality seat
    }),
    month_forms=IT_MONTHS,  # "nell'aprile 1945": the same words
)

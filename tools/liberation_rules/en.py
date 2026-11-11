"""English: town articles of the Philippines, Burma, Malaya, the Dutch East Indies and China
that say when the place was liberated from Japan in 1944–45 ("liberated by combined Filipino and
American forces on February 3, 1945", "recaptured by the 14th Army").

The country follows from where the place lies (rough boxes, checked in order). The occupation is
the Japanese one of December 1941 – 1942 when the article dates it ("occupied by the Japanese on
December 24, 1941"). English writes "February 3, 1945" as well as "3 February 1945".
"""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule

EN_MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}

def country_of(lat, lng):
    """The country of 1941–45 a place lies in, roughly; None for one Japan never lost by fighting
    (Thailand, Indochina, Korea, Taiwan, Japan) or one outside the five."""
    if 4.5 <= lat <= 21.5 and 116.5 <= lng <= 127.0 and not (lat < 7.2 and lng < 119.5):  # not Sabah
        return "Filipijnen"
    if 9.5 <= lat <= 28.6 and 92.2 <= lng <= 101.2:
        if lng > 98.7 and lat < 20.3:            # Thailand
            return None
        if (lat > 23.5 and lng > 98.0) or (lat > 21.5 and lng > 98.8):  # Yunnan
            return "China"
        if (lat > 23.0 and lng < 94.6) or (lat < 16.0 and lng < 94.0):  # India: Manipur, the Andamans
            return None
        return "Birma"
    if 1.2 <= lat <= 6.8 and 100.1 <= lng <= 104.6 and (lat >= 2.5 or lng >= 101.8):
        return "Malakka"
    if 1.0 <= lat <= 7.5 and 109.5 <= lng <= 119.3 and lat > 1.0 + (lng - 109.5) * 0.42:
        return "Brits-Borneo"  # Sarawak, Brunei, North Borneo
    if -9.5 <= lat <= -8.1 and 124.9 <= lng <= 127.4:  # Portuguese Timor
        return None
    if -11.0 <= lat <= 6.0 and 95.0 <= lng <= 141.1:
        return "Nederlands-Indië"
    if 18.0 <= lat <= 54.0 and 97.5 <= lng <= 135.0:
        if lat < 23.5 and lng < 106.0:            # Indochina and Laos
            return None
        if lat < 22.5 and 102.0 < lng < 108.0:  # northern Vietnam
            return None
        if 21.8 <= lat <= 25.4 and 119.9 <= lng <= 122.1:  # Taiwan
            return None
        if lat < 39.5 and lng > 123.0:           # Korea, Japan
            return None
        if lng > 124.3 and lat < 40.0 + (lng - 124.4) * 0.55:  # Korea below the Yalu and Tumen
            return None
        if lng > 131.0 and lat < 47.5:          # the Soviet Far East
            return None
        if lat > 42.0 and lng < 115.0:           # Mongolia
            return None
        return "China"
    return None


def manchuria(lat, lng):
    """Manchuria and Rehe, taken by the Red Army in August 1945."""
    return lat > 39.0 and lng > 117.0


# Many Philippine town articles share a sentence on when the Commonwealth Army and Constabulary
# were "active from October 28, 1944, to June 30, 1946"; its dates are not the town's.
BOILERPLATE = re.compile(r"\bactive from\b|\bstationed\b|re-?established|\bfrom January 1, to\b", re.IGNORECASE)


def english_dates(sentence, months):
    """"February 3, 1945", "3 February 1945", "3rd of February 1945": (position, ISO date)."""
    if BOILERPLATE.search(sentence):
        return []
    pattern = "|".join(months)
    text = sentence.lower()
    found = []
    for match in re.finditer(
            rf"\b(?:({pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?|(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({pattern}),?)"
            rf"(?:\s+(\d{{4}}))?", text):
        month = match.group(1) or match.group(4)
        day = match.group(2) or match.group(3)
        year = match.group(5)
        if year is None:
            later = re.search(r"\b(19[34]\d)\b", text[match.end():match.end() + 40])
            year = later.group(1) if later else None
        if year is None:
            continue
        try:
            date = dt.date(int(year), months[month], int(day))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    return found


def _adjust(b):
    country = country_of(b.lat, b.lng)
    if country is None:
        return None
    b.country = country
    # December 7, 1941 is Pearl Harbor, not the day a town was occupied.
    if b.occupied is not None and b.occupied < "1941-12-08":
        b.occupied = None
    if country == "China":
        # China was occupied from 1937 on; a date of 1941–42 is about something else.
        b.occupied = None
        if manchuria(b.lat, b.lng) and b.liberated >= "1945-08-09":
            b.kamp = "sovjet"
    return b


RULE = ArticleRule(
    lang="en",
    country="Filipijnen",
    kamp="westers",
    source="en-articles",
    # "OR" widens CirrusSearch far beyond either word, so one word per query.
    queries=(
        "liberated 1945 Japanese municipality Philippines",
        "liberated 1945 Japanese barangay",
        "liberated 1944 Japanese Leyte",
        "liberated 1945 Japanese town Burma",
        "recaptured 1945 Japanese town Burma",
        "liberated 1945 Japanese Indonesia town",
        "liberated 1945 Japanese Malaya town",
        "liberated 1945 Japanese Borneo town",
        "recaptured 1945 Japanese China county",
        "recaptured 1944 Japanese China county",
    ),
    liberated=re.compile(r"\b(?:liberat(?:ed|ion|ing)|recaptured?|retaken|retook|freed)\b", re.IGNORECASE),
    occupied=re.compile(r"\b(?:occupied|occupation|invaded|invasion|captured|fell)\b", re.IGNORECASE),
    months=EN_MONTHS,
    area=(-11.0, 54.0, 73.0, 141.1),
    first_liberation=1944,
    occupation_years=(1941, 1942),
    dates=english_dates,
    # "liberated in October 1944": the same names, kept apart when no day is given.
    month_forms=EN_MONTHS,
    settlements=frozenset({
        "Q24764",     # municipality of the Philippines
        "Q29946056",  # component city of the Philippines
        "Q104157",    # city of the Philippines
    }),
    adjust=_adjust,
)

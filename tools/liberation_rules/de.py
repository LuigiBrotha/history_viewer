"""German: town and village articles of Germany in its borders of 1937 that say when the place
was taken in 1944–45 ("am 12. April 1945 von amerikanischen Truppen besetzt", "am 9. März 1945
von der Roten Armee besetzt", "kampflos").

Germany was an Axis country, so the places were taken ("ingenomen"), not liberated, and there is
no occupation date. The villages of Pomerania, Silesia and East Prussia (Polish or Russian today)
count as well, under Germany as during the war, as the Russian list does for its towns; Alsace,
Austria and the Sudetenland do not. Who took them follows from where they lie: east of the line where the armies
met in 1945 (Wismar, the Elbe to Magdeburg, the Mulde, Chemnitz) the Red Army, west of it the
Western Allies.
"""

import datetime as dt
import re

from tools import liberations as lists
from tools.liberation_articles import ArticleRule

DE_MONTHS = {m: i for i, m in enumerate(
    "januar februar märz april mai juni juli august september oktober november dezember".split(), 1)}
DE_MONTHS["jänner"] = 1

# Germany in its borders of 1937, roughly (lat, lng), clockwise from the Dutch border at the Ems.
GERMANY_1937 = [
    (53.60, 7.00), (53.30, 7.21), (52.65, 7.05), (52.43, 7.07), (52.13, 7.06), (52.00, 6.83),
    (51.84, 6.40), (51.86, 6.10), (51.76, 5.97), (51.70, 6.05), (51.50, 6.10), (51.37, 6.22),
    (51.17, 6.17), (51.05, 5.98), (50.95, 6.00), (50.87, 6.08), (50.75, 6.02), (50.65, 6.27),
    (50.42, 6.40), (50.32, 6.38), (50.13, 6.13), (49.80, 6.50), (49.47, 6.37), (49.20, 6.75),
    (49.10, 7.05), (49.05, 7.60), (48.97, 8.20), (48.60, 7.82), (48.20, 7.62), (47.60, 7.55),
    (47.56, 8.20), (47.62, 8.60), (47.66, 9.17), (47.52, 9.60), (47.40, 10.20), (47.30, 10.90),
    (47.55, 11.40), (47.62, 12.20), (47.70, 13.00), (48.15, 12.95), (48.30, 13.40), (48.60, 13.80),
    (48.80, 13.60), (49.30, 12.80), (49.90, 12.40), (50.30, 12.10), (50.50, 13.20), (50.75, 14.00),
    (50.90, 14.40), (50.85, 15.00), (50.75, 15.80), (50.50, 16.20), (50.20, 16.80), (50.40, 17.00),
    (50.30, 17.70), (50.00, 18.00), (50.15, 18.50), (50.30, 18.75), (50.60, 18.80), (51.00, 18.30),
    (51.30, 18.00), (51.60, 17.20), (51.70, 16.60), (52.10, 16.00), (52.50, 15.95), (52.90, 16.10),
    (53.05, 16.80), (53.40, 17.20), (53.70, 17.45), (54.15, 17.90), (54.55, 17.90), (54.85, 17.95),
    (54.70, 16.50), (54.60, 14.30), (54.80, 13.40), (54.50, 12.30), (54.20, 11.00), (54.50, 10.20),
    (54.83, 9.95),
    (54.83, 8.60), (55.10, 8.30), (54.40, 8.40), (53.90, 8.00),
]


# East Prussia with the Marienwerder district, beyond the Polish Corridor; without Danzig and the
# Memel land, which were not German in 1937.
EAST_PRUSSIA = [
    (54.45, 19.20), (54.10, 19.00), (53.90, 18.85), (53.45, 18.75), (53.30, 19.50), (53.20, 20.50),
    (53.30, 21.50), (53.50, 22.50), (54.35, 22.80), (55.07, 22.90), (55.08, 21.90), (55.30, 21.25),
    (55.30, 20.95), (54.95, 20.00), (54.65, 19.85),
]


def german_1937(lat, lng):
    """True when the place lay in Germany in its borders of 1937."""
    return lists.inside(GERMANY_1937, lat, lng) or lists.inside(EAST_PRUSSIA, lat, lng)


# The meeting line of 1945, north to south (lat, lng); east of it the Red Army took the places.
MEETING_LINE = [
    (56.5, 11.45), (53.90, 11.45), (53.60, 11.40), (53.15, 11.20), (53.00, 11.75), (52.54, 11.97),
    (52.13, 11.65), (51.97, 11.88), (51.83, 12.25), (51.62, 12.33), (51.37, 12.74), (51.13, 12.81),
    (50.83, 12.92), (50.50, 12.95), (50.20, 12.95),
]


def soviet_side(lat, lng):
    """True when the place lies east of the meeting line."""
    if lat > MEETING_LINE[0][0]:
        return False
    if lat < MEETING_LINE[-1][0]:
        return False  # Bavaria: the US Army
    for (lat1, lng1), (lat2, lng2) in zip(MEETING_LINE, MEETING_LINE[1:]):
        if lat2 <= lat <= lat1:
            border = lng1 + (lat - lat1) * (lng2 - lng1) / (lat2 - lat1)
            return lng > border
    return False


def german_dates(sentence, months):
    """"12. April 1945", "am 3. Mai" (year later in the sentence): (position, ISO date)."""
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
    return found


def _adjust(b):
    # After the capitulation a date is the handing over of a zone or the expulsions, not a taking.
    if not german_1937(b.lat, b.lng) or b.liberated > "1945-05-15":
        return None
    b.kamp = "sovjet" if soviet_side(b.lat, b.lng) else "westers"
    return b


RULE = ArticleRule(
    lang="de",
    country="Duitsland",
    kamp="westers",
    source="de-articles",
    # Regex searches for a dotted date followed by the taking: plain word searches find ten
    # thousand articles (people, units), these a few thousand, nearly all places.
    queries=(
        r"insource:/[0-9]\. (März|April|Mai) 1945[^.]{0,60}(besetzt|eingenommen|einmarschiert)/",
        r"insource:/[0-9]\. (Februar|März|April|Mai) 1945[^.]{0,80}(Rote Armee|Roten Armee|sowjetische Truppen"
        r"|amerikanische Truppen|US-Truppen|britische Truppen|französische Truppen)/",
        r"insource:/[0-9]\. (September|Oktober|November|Dezember) 1944[^.]{0,60}(besetzt|eingenommen)/",
    ),
    liberated=re.compile(
        r"\b(?:eingenommen|besetzt(?:en|e)?|einmarsch|einmarschiert|eingerückt|rückten|erobert|"
        r"kampflos|befreit|eroberten|nahmen)\b", re.IGNORECASE),
    occupied=None,
    months=DE_MONTHS,
    # Germany in its borders of 1937 (GERMANY_1937 decides).
    area=(47.2, 56.0, 5.8, 23.0),
    first_liberation=1944,
    verb="ingenomen",
    dates=german_dates,
    settlements=frozenset({
        "Q262166",     # municipality of Germany
        "Q42744322",   # urban municipality of Germany
        "Q116457956",  # non-urban municipality of Germany
        "Q253019",     # Ortsteil
        "Q3558970",    # village of Poland (the former German east)
        "Q2616791",    # urban municipality of Poland
    }),
    # "im April 1945 besetzt": the same names, kept apart when no day is given.
    month_forms=DE_MONTHS,
    adjust=_adjust,
    last_liberation="1945-05-31",
)

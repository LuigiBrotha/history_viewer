"""Polish: village and town articles that say when the Red Army (with the Polish 1st Army) came
("wkroczyła Armia Czerwona", "wyzwolona", "zajęta przez Armię Czerwoną").

Only inside interwar Poland was a place occupied (September 1939, east of the Bug line June 1941)
and liberated; a town that was German before 1945 (Silesia, Pomerania, East Prussia) was taken,
without occupation, and counts under Germany, as the lists do."""

import re

from tools.liberation_articles import ArticleRule, _dates
from tools.liberation_rules.cs import CZECH_LANDS, SLOVAKIA
from tools.liberations import inside, wartime_country

PL_MONTHS = {m: i for i, m in enumerate(
    "stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia".split(), 1)}
# A month without a day: "w styczniu 1945".
PL_MONTH_FORMS = {m: i for i, m in enumerate(
    "styczniu lutym marcu kwietniu maju czerwcu lipcu sierpniu wrześniu październiku listopadzie grudniu".split(), 1)}


# Today's border of Poland in the west (the Oder and Neisse) and the east (the Bug), as (lat, lng)
# from north to south; the Czech and Slovak border is left to their outlines.
WEST = [(54.0, 14.2), (53.5, 14.3), (52.85, 14.13), (52.6, 14.6), (52.35, 14.55), (51.95, 14.72), (51.6, 14.72),
        (51.2, 15.03), (50.85, 14.83)]
EAST = [(54.36, 22.8), (53.95, 23.5), (53.5, 23.9), (52.7, 23.95), (52.1, 23.65), (51.55, 23.6), (51.2, 23.85),
        (50.8, 24.1), (50.4, 23.95), (50.1, 23.4), (49.8, 22.95), (49.0, 22.85)]


def _along(line, lat):
    """The longitude of a north–south border line at `lat` (its ends extended)."""
    for (lat1, lng1), (lat2, lng2) in zip(line, line[1:]):
        if lat2 <= lat <= lat1:
            return lng1 + (lat - lat1) * (lng2 - lng1) / (lat2 - lat1)
    return line[0][1] if lat > line[0][0] else line[-1][1]


def in_poland(lat, lng):
    """Inside today's Poland, roughly: not Germany, Kaliningrad, Lithuania, Belarus, Ukraine, the
    Czech lands or Slovakia."""
    if lng < _along(WEST, lat) or lng > _along(EAST, lat) or (lat > 54.42 and lng > 19.6):
        return False
    return not (inside(CZECH_LANDS, lat, lng) or inside(SLOVAKIA, lat, lng))


def war_dates(sentence, months):
    """The day-month-year dates of a sentence up to the end of the war in Europe: a later one (an
    attack of the UPA on New Year's Eve 1945) is no liberation."""
    return [(at, iso) for at, iso in _dates(sentence, months) if iso <= "1945-05-31"]


def _wartime(b):
    """A place outside today's Poland is left to its own language; a town outside interwar Poland
    was German: taken, never occupied."""
    if not in_poland(b.lat, b.lng):
        return None
    wartime = wartime_country(b.country, b.lat, b.lng)
    if wartime:
        b.country, b.verb = wartime
        b.occupied = None
    return b


RULE = ArticleRule(
    lang="pl",
    country="Polen",
    kamp="sovjet",
    source="pl-articles",
    queries=(
        "wkroczyła Armia Czerwona 1945", "wkroczyła Armia Czerwona 1944",
        "wkroczyły wojska radzieckie 1945", "wkroczyły wojska radzieckie 1944",
        "wyzwolona 1945 wieś", "wyzwolona 1944 wieś", "wyzwolenie 1945 wieś",
        "zajęta przez Armię Czerwoną 1945",
        # The wording of many village articles: "Okupację niemiecką X zakończyło 2 sierpnia 1944
        # roku zajęcie miejscowości przez wojska 60 Armii", "X leżące w granicach III Rzeszy 27
        # stycznia 1945 roku zdobyły wojska 50 Armii".
        "okupację niemiecką zakończyło zajęcie miejscowości przez wojska",
        "okupację niemiecką zakończyło zdobycie miejscowości",
        "w granicach III Rzeszy zdobyły wojska Armii Czerwonej",
        "w granicach III Rzeszy zajęły wojska Armii Czerwonej",
    ),
    # The Red Army came, entered, took or freed the place; the year (1944–1945) keeps out the
    # Soviet entry of September 1939 and the Germans of 1939.
    liberated=re.compile(
        r"wyzwol|wkroczy|zaj[eę][łltc]|zdoby|opanowa|Armi[aię] Czerwon|wojska radzieck|wojska sowieck|front przesz|przesz[eł]+ front",
        re.IGNORECASE),
    # Only the Germans occupied: the Soviet entry of 17 September 1939 is no occupation here.
    occupied=re.compile(
        r"(wkroczy|zaj[eę][łltc]|zdoby|opanowa|wesz[łl])\w*( \w+){0,4} (Niem|niemieck|hitlerow|Wehrmacht)"
        r"|(Niemcy|Niemców|niemieckie|Wehrmacht)( \w+){0,3} (wkroczy|zaj[eę]|zdoby|opanowa|wesz[łl])"
        r"|okupac\w*( \w+){0,3} (niemieck|hitlerow|Niem|wojsk\w* niem)|(niemieck|hitlerow)\w* okupac",
        re.IGNORECASE),
    months=PL_MONTHS,
    # Poland within its borders of today, roughly.
    area=(49.0, 54.9, 14.1, 24.2),
    first_liberation=1944,
    occupation_years=(1939, 1941),
    settlements=frozenset({
        "Q3558970",    # village of Poland
        "Q2616791",    # urban municipality of Poland (a town)
        "Q925381",     # city with powiat rights
        "Q13416557",   # town of Poland (seat of a powiat)
        "Q2983893",    # quarter (a former village within a town)
        "Q1434401",    # osiedle (a former village within a town)
    }),
    dates=war_dates,
    adjust=_wartime,
    month_forms=PL_MONTH_FORMS,
    last_liberation="1945-05-31",
)

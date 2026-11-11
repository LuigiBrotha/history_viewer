"""Dutch: village articles of the Netherlands and Flanders that say when the place was liberated
("werd op 14 september 1944 bevrijd", "de bevrijding op 2 oktober 1944").

The lists already hold 867 Dutch places and 35 Belgian ones, so this adds the smaller villages.
One rule for both countries; where a place lies decides the country (two rough border polygons),
and a place in neither (a German or French village with a Dutch article) is dropped. The
Flemish articles mostly date the occupation ("werd rond 23 mei 1940 bezet"), the Dutch ones
seldom: the frontend gives the Netherlands 10 May 1940; Belgium has no default yet.
"""

import re

from tools import liberations as lists
from tools.liberation_articles import ArticleRule

NL_MONTHS = {m: i for i, m in enumerate(
    "januari februari maart april mei juni juli augustus september oktober november december".split(), 1)}

# Rough borders (lat, lng): within a few km, enough to tell a Dutch from a Belgian village.
BELGIUM = [
    (51.08, 2.50), (51.30, 2.90), (51.40, 3.36), (51.28, 3.38), (51.27, 3.55), (51.25, 3.70), (51.24, 3.76), (51.21, 3.80), (51.27, 4.05),
    (51.37, 4.24), (51.37, 4.38), (51.50, 4.48), (51.43, 4.62), (51.49, 4.80), (51.43, 4.93),
    (51.47, 5.05), (51.27, 5.30), (51.24, 5.50), (51.18, 5.85), (51.10, 5.83),
    (50.98, 5.76), (50.85, 5.64), (50.75, 5.69), (50.75, 6.02), (50.65, 6.27), (50.42, 6.40),
    (50.32, 6.38), (50.13, 6.13), (49.92, 5.78), (49.55, 5.92), (49.50, 5.47), (49.55, 5.10),
    (49.80, 4.85), (50.15, 4.82), (49.97, 4.45), (50.00, 4.15), (50.32, 4.02), (50.45, 3.65),
    (50.50, 3.28), (50.72, 3.15), (50.78, 2.90), (50.70, 2.65), (50.95, 2.60),
]
NETHERLANDS = [
    (51.37, 3.36), (51.28, 3.38), (51.27, 3.55), (51.25, 3.70), (51.24, 3.76), (51.21, 3.80), (51.27, 4.05), (51.37, 4.24),
    (51.37, 4.38), (51.50, 4.48), (51.43, 4.62), (51.49, 4.80), (51.43, 4.93), (51.47, 5.05),
    (51.27, 5.30), (51.24, 5.50), (51.18, 5.85), (51.10, 5.83), (50.98, 5.76),
    (50.85, 5.64), (50.75, 5.69), (50.75, 6.02), (50.87, 6.08), (50.95, 6.00), (51.05, 5.98),
    (51.17, 6.17), (51.37, 6.22), (51.50, 6.10), (51.70, 6.05), (51.76, 5.97), (51.86, 6.10),
    (51.84, 6.40), (52.00, 6.83), (52.13, 7.06), (52.43, 7.07), (52.65, 7.05), (53.00, 7.21),
    (53.30, 7.21), (53.60, 6.90), (53.60, 4.70), (53.00, 4.55), (52.30, 4.40), (51.85, 3.80),
]


def _adjust(b):
    if lists.inside(BELGIUM, b.lat, b.lng):
        b.country = "België"
    elif not lists.inside(NETHERLANDS, b.lat, b.lng):
        return None
    return b


RULE = ArticleRule(
    lang="nl",
    country="Nederland",
    kamp="westers",
    source="nl-articles",
    queries=("bevrijd 1944 dorp", "bevrijd 1945 -1944 dorp", "bevrijd 1944 deelgemeente",
             'bevrijd 1944 hastemplate:"Infobox plaats in Nederland"'),
    # "bevrijd", "bevrijdde", "bevrijding"; not a prisoner "bevrijd uit" a camp, nor "na de" or
    # "voor de bevrijding" with the date of something else.
    liberated=re.compile(r"(?<!na de )(?<!voor de )\bbevrijd(?:e|de|den|ing)?\b(?!\s+uit\b)", re.IGNORECASE),
    # The Flemish articles say "werd rond 23 mei 1940 bezet door het Duitse leger".
    occupied=re.compile(r"\bbezet\b", re.IGNORECASE),
    months=NL_MONTHS,
    # The Netherlands and Belgium.
    area=(49.4, 53.6, 2.5, 7.3),
    first_liberation=1944,
    occupation_years=(1940, 1940),
    settlements=frozenset({
        "Q493522",    # municipality of Belgium
        "Q2785216",   # section of a municipality of Belgium (deelgemeente)
        "Q15273785",  # city of Belgium
        "Q2039348",   # municipality of the Netherlands
        "Q1852859",   # populated place in the Netherlands
        "Q13539802",  # place in the Netherlands
        "Q1484611",   # hamlet (buurtschap)
    }),
    adjust=_adjust,
)

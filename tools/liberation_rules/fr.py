"""French: commune articles that say when the place was liberated ("la commune est libérée le
{{date|2 septembre 1944}}", "le village a été libéré le …").

Only the singular counts: "libérés"/"libérées" is nearly always hostages or deportees set free,
and so is "libéré du camp" or "de prison". The occupation is the article's own date ("occupée par
les Allemands le …") or else the date the lists use: 1940 north of the demarcation line, 11
November 1942 south of it. Corsica was liberated in 1943; a 1943 date elsewhere is no liberation.
"""

import re

from tools import liberations as lists
from tools.liberation_articles import ArticleRule, _dates

FR_MONTHS = {m: i for i, m in enumerate(
    "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split(), 1)}

COMMUNES = 'hastemplate:"Infobox Commune de France"'


# A sentence about people set free (prisoners, deportees, hostages) or a decoration holds no
# date of the place.
PEOPLE = re.compile(r"prisonni|déport|otage|captivit|convoi|croix|médaille|compagnon", re.IGNORECASE)


def french_dates(sentence, months):
    """The day-month-year dates of a sentence, none in one about people set free."""
    return [] if PEOPLE.search(sentence) else _dates(sentence, months)


def _adjust(b):
    if b.liberated < "1944" and b.lng < 8.0:
        return None
    if b.occupied is None:
        b.occupied = lists.french_occupation(b.lat, b.lng)
    return b


RULE = ArticleRule(
    lang="fr",
    country="Frankrijk",
    kamp="westers",
    source="fr-articles",
    queries=(f"{COMMUNES} libérée 1944", f"{COMMUNES} libérée 1945 -1944", f"{COMMUNES} libérée 1943 Corse"),
    # The verb, or "la libération de la ville": the noun alone is mostly the period ("à la
    # Libération") or a decoration ("Croix de la Libération").
    liberated=re.compile(
        r"\b(?:libér(?:ée?|ant|èrent|ent)|libèrent?|libération (?:de la (?:ville|commune|localité)|du (?:village|bourg)))\b"
        r"(?!\s+(?:du|des|de la|de|d')\s*(?:camps?|prison|stalag|oflag|captivité))",
        re.IGNORECASE),
    occupied=re.compile(r"\boccup(?:ée?|ent|èrent|ation)\b|\bentr(?:ent|èrent)\s+dans", re.IGNORECASE),
    months=FR_MONTHS,
    # Metropolitan France with Corsica.
    area=(41.3, 51.2, -5.2, 9.6),
    first_liberation=1943,
    occupation_years=(1940, 1942),
    settlements=frozenset({"Q484170"}),  # commune of France
    dates=french_dates,
    # "libérée en septembre 1944": the same names, kept apart when no day is given.
    month_forms=FR_MONTHS,
    adjust=_adjust,
    last_liberation="1945-05-31",
)

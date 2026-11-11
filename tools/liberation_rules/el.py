"""Greek: village and town articles that say when the place was liberated ("απελευθερώθηκε στις
12 Οκτωβρίου 1944"). The Germans, Italians and Bulgarians occupied Greece in April–May 1941; the
liberation came in October–November 1944 (Crete and the Dodecanese in May 1945). An earlier
"απελευθέρωση" is that of the Balkan wars (1912–1913) and falls outside the years. The
liberators, the British and the resistance (ELAS, EDES), count as "westers".
"""

import re

from tools.liberation_articles import ArticleRule

EL_MONTHS = {
    "ιανουαρίου": 1, "φεβρουαρίου": 2, "μαρτίου": 3, "απριλίου": 4, "μαΐου": 5, "μαίου": 5,
    "ιουνίου": 6, "ιουλίου": 7, "αυγούστου": 8, "σεπτεμβρίου": 9, "οκτωβρίου": 10,
    "νοεμβρίου": 11, "δεκεμβρίου": 12,
    # The spoken forms.
    "γενάρη": 1, "φλεβάρη": 2, "μάρτη": 3, "απρίλη": 4, "σεπτέμβρη": 9, "οκτώβρη": 10,
    "νοέμβρη": 11, "δεκέμβρη": 12,
}

# Greece's northern border, west to east, roughly: (latitude, longitude). The area's box also
# holds southern Albania, North Macedonia and Bulgaria, whose towns have Greek articles too.
NORTH_BORDER = ((39.85, 19.3), (39.82, 19.95), (39.65, 20.05), (40.4, 20.65), (40.85, 21.0),
                (41.1, 22.0), (41.25, 22.8), (41.45, 23.5), (41.6, 24.5), (41.35, 25.3),
                (41.7, 26.2), (41.75, 26.65))


def _border_at(lng):
    for (lat1, lng1), (lat2, lng2) in zip(NORTH_BORDER, NORTH_BORDER[1:]):
        if lng1 <= lng <= lng2:
            return lat1 + (lat2 - lat1) * (lng - lng1) / (lng2 - lng1)
    return NORTH_BORDER[0][0] if lng < NORTH_BORDER[0][1] else NORTH_BORDER[-1][0]


def adjust(b):
    """Only a place south of Greece's northern border (and west of Turkey) is Greek."""
    if b.lat > _border_at(b.lng) or (b.lng > 26.65 and b.lat > 40.3):
        return None
    return b

# A month without a day: "τον Οκτώβριο του 1944" (accusative) or "τέλη Οκτωβρίου 1944".
EL_MONTH_FORMS = {m: i for i, m in enumerate(
    "ιανουάριο φεβρουάριο μάρτιο απρίλιο μάιο ιούνιο ιούλιο αύγουστο σεπτέμβριο οκτώβριο νοέμβριο δεκέμβριο".split(), 1)}
EL_MONTH_FORMS |= EL_MONTHS


RULE = ArticleRule(
    lang="el",
    country="Griekenland",
    kamp="westers",
    source="el-articles",
    queries=(
        "insource:/απελευθερώθηκ/ 1944",
        "insource:/απελευθερώθηκ/ 1945",
        "insource:/απελευθέρωση/ insource:/(Οκτωβρίου|Σεπτεμβρίου|Νοεμβρίου) 1944/",
    ),
    liberated=re.compile(r"απελευθερ|ελευθερώθηκ", re.IGNORECASE),
    occupied=re.compile(r"κατοχ|καταλήφθηκ|κατελήφθ|κατέλαβ|εισήλθαν|μπήκαν", re.IGNORECASE),
    months=EL_MONTHS,
    first_liberation=1944,
    occupation_years=(1941, 1941),
    # Greece within its borders of today, roughly (Crete and the Dodecanese included).
    area=(34.7, 41.8, 19.3, 29.7),
    adjust=adjust,
    month_forms=EL_MONTH_FORMS,
)

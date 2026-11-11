"""Croatian: village and town articles of Croatia and Bosnia that say when the partisans
liberated the place ("oslobođen 8. svibnja 1945.").

Many places were liberated, lost and liberated again from 1941 on (the Bihać republic of 1942);
only 1944–1945, the final liberation, counts. The occupation (Germans, Italians, the Ustaša NDH)
began in April 1941. The partisans count as "westers": they were the Allies' army in Yugoslavia,
not the Red Army. sh.wikipedia covers the same places and is left out; sr.wikipedia's rule covers
Serbia, Montenegro and Bosnia, and the build drops a place an earlier rule already has (3 km,
3 days).
"""

import datetime as dt
import re

from tools.liberation_articles import ArticleRule


# "Finally": "liberated on 9 September, and finally on 3 November" — the dates before it are a
# liberation that did not last.
FINALLY = re.compile(r"\b(?:konačn|коначн|конечн|дефинитивн|definitivn|dokončn)\w*", re.IGNORECASE)


def dated(sentence, months):
    """Every date of a South Slavic article: "20. oktobra 1944", "20 октомври 1944",
    "20.10.1944." and "1. V. 1945": (position, ISO date). After a "finally" only the dates that
    follow it count."""
    text = sentence.lower()
    final = FINALLY.search(text)
    pattern = "|".join(sorted(months, key=len, reverse=True))
    roman = "xii|xi|x|ix|viii|vii|vi|v|iv|iii|ii|i"
    numerals = {r: i for i, r in enumerate("i ii iii iv v vi vii viii ix x xi xii".split(), 1)}
    found = []
    for match in re.finditer(
            rf"(?<![\d.])(\d{{1,2}})\.?\s*(?:({pattern})(?![^\W\d_])|(\d{{1,2}})\.|({roman})\.)\s*(\d{{4}})?", text):
        year = match.group(5)
        if match.group(2) is None and year is None:
            continue  # "20.10." alone could be anything
        if year is None:
            later = re.search(r"\b(19[34]\d)\b", text[match.end():match.end() + 40])
            # "... on 9 September 1944, and finally on 3 November the same year"
            year = later.group(1) if later else found[-1][1][:4] if found else None
        if year is None:
            continue
        month = (months[match.group(2)] if match.group(2) else
                 int(match.group(3)) if match.group(3) else numerals[match.group(4)])
        try:
            date = dt.date(int(year), month, int(match.group(1)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    if final and any(at > final.start() for at, _ in found):
        found = [(at, iso) for at, iso in found if at > final.start()]
    return found


# The Croatian month names and, as many articles use them too, the Serbian ones.
HR_MONTHS = {m: i for i, m in enumerate(
    "siječnja veljače ožujka travnja svibnja lipnja srpnja kolovoza rujna listopada studenoga prosinca".split(), 1)}
HR_MONTHS |= {"studenog": 11, "sijecnja": 1, "veljace": 2, "ozujka": 3}
HR_MONTHS |= {m: i for i, m in enumerate(
    "januara februara marta aprila maja juna jula augusta septembra oktobra novembra decembra".split(), 1)}
HR_MONTHS |= {"avgusta": 8}

# The verb and participle; the noun only in "dan oslobođenja" (the day of liberation): "u borbama
# za oslobođenje Beograda" in a village's article is someone's death, not the village's liberation.
LIBERATED = re.compile(r"\boslobođen[aoi]?\b|\boslobodi(?:l[aie]?|še|o)?\b|\bdan[a]? oslobođenja\b|"
                       r"\bослобођен[аои]?\b|\bослободи(?:л[аие]?|ше|о)?\b|\bдан[а]? ослобођења\b", re.IGNORECASE)
OCCUPIED = re.compile(r"\bokupira\w*|\bokupacij\w*|\bzauze\w*|\bzaposje\w*|\bušl[aie]\b|"
                      r"\bокупира\w*|\bокупациј\w*|\bзаузе\w*|\bушл[аие]\b", re.IGNORECASE)
# A month without a day stands in the locative: "u travnju 1945", "u aprilu 1945".
HR_MONTH_FORMS = {m: i for i, m in enumerate(
    "siječnju veljači ožujku travnju svibnju lipnju srpnju kolovozu rujnu listopadu studenom prosincu".split(), 1)}
HR_MONTH_FORMS |= {"studenome": 11}
HR_MONTH_FORMS |= {m: i for i, m in enumerate(
    "januaru februaru martu aprilu maju junu julu augustu septembru oktobru novembru decembru".split(), 1)}
HR_MONTH_FORMS |= {"avgustu": 8}


RULE = ArticleRule(
    lang="hr",
    country="Joegoslavië",
    kamp="westers",
    source="hr-articles",
    queries=("insource:/oslobođen/ 1944", "insource:/oslobođen/ 1945"),
    liberated=LIBERATED,
    occupied=OCCUPIED,
    months=HR_MONTHS,
    first_liberation=1944,
    occupation_years=(1941, 1941),
    # Croatia and Bosnia-Herzegovina, roughly.
    area=(42.3, 46.6, 13.4, 19.7),
    dates=dated,
    settlements=frozenset({
        "Q15105893",  # town in Croatia
        "Q57058",     # municipality of Croatia (named after its main village)
        "Q4845841",   # settlement of Croatia
    }),
    month_forms=HR_MONTH_FORMS,
    last_liberation="1945-05-31",
)

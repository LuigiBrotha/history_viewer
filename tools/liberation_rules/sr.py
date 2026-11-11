"""Serbian: village and town articles of Serbia, Montenegro and Bosnia that say when the place was
liberated ("ослобођен 20. октобра 1944.").

Only 1944–1945 counts: the Užice republic of 1941 was lost again within weeks. The occupation
began in April 1941. The partisans count as "westers"; the Red Army that fought beside them for
Belgrade and the north-east (October 1944) is not told apart, the article's place gives no
reliable line. Croatia is hr.wikipedia's (its rule runs first; a place it already has within
3 km and 3 days is dropped).
"""

import re

from tools.liberation_articles import ArticleRule
from tools.liberation_rules.hr import LIBERATED, OCCUPIED, dated

SR_MONTHS = {m: i for i, m in enumerate(
    "јануара фебруара марта априла маја јуна јула августа септембра октобра новембра децембра".split(), 1)}
SR_MONTHS |= {m: i for i, m in enumerate(
    "januara februara marta aprila maja juna jula avgusta septembra oktobra novembra decembra".split(), 1)}
SR_MONTHS |= {"augusta": 8}
# A month without a day stands in the locative: "у октобру 1944", "u oktobru 1944".
SR_MONTH_FORMS = {m: i for i, m in enumerate(
    "јануару фебруару марту априлу мају јуну јулу августу септембру октобру новембру децембру".split(), 1)}
SR_MONTH_FORMS |= {m: i for i, m in enumerate(
    "januaru februaru martu aprilu maju junu julu avgustu septembru oktobru novembru decembru".split(), 1)}
SR_MONTH_FORMS |= {"augustu": 8}


RULE = ArticleRule(
    lang="sr",
    country="Joegoslavië",
    kamp="westers",
    source="sr-articles",
    queries=("insource:/ослобођен/ 1944", "insource:/ослобођен/ 1945",
             "insource:/oslobođen/ 1944", "insource:/oslobođen/ 1945"),
    liberated=LIBERATED,
    occupied=OCCUPIED,
    months=SR_MONTHS,
    first_liberation=1944,
    occupation_years=(1941, 1941),
    # Serbia (with Kosovo), Montenegro and Bosnia-Herzegovina, roughly.
    area=(41.8, 46.2, 15.7, 23.1),
    dates=dated,
    settlements=frozenset({
        "Q37800986",  # city of Serbia
    }),
    month_forms=SR_MONTH_FORMS,
    last_liberation="1945-05-31",
)

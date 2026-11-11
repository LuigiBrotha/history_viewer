"""Macedonian: village and town articles that say when the place was liberated ("ослободен на 13
ноември 1944"). Bulgaria (and Italy in the west) occupied Vardar Macedonia in April 1941; the
partisans liberated it in October–November 1944. They count as "westers"."""

import re

from tools.liberation_articles import ArticleRule
from tools.liberation_rules.hr import dated

MK_MONTHS = {m: i for i, m in enumerate(
    "јануари февруари март април мај јуни јули август септември октомври ноември декември".split(), 1)}

RULE = ArticleRule(
    lang="mk",
    country="Joegoslavië",
    kamp="westers",
    source="mk-articles",
    queries=("insource:/ослободен/ 1944",),
    liberated=re.compile(r"\bослобод(?:ен|ено|ена|ени|ување|увањето|и|ија|иле)\b", re.IGNORECASE),
    occupied=re.compile(r"\bокупира\w*|\bокупациј\w*|\bзазема\w*|\bзазеде\w*|\bвлего\w*", re.IGNORECASE),
    months=MK_MONTHS,
    first_liberation=1944,
    occupation_years=(1941, 1941),
    # North Macedonia, roughly.
    area=(40.8, 42.4, 20.4, 23.1),
    dates=dated,
    month_forms=MK_MONTHS,  # "во ноември 1944": the same words
)

"""Ukrainian: village and town articles that say when the place was liberated ("звільнено від
німецьких окупантів", "визволили")."""

import re

from tools.liberation_articles import ArticleRule

UK_MONTHS = {m: i for i, m in enumerate(
    "січня лютого березня квітня травня червня липня серпня вересня жовтня листопада грудня".split(), 1)}

RULE = ArticleRule(
    lang="uk",
    country="Sovjet-Unie",
    kamp="sovjet",
    source="uk-articles",
    queries=tuple(
        f"insource:/(звільнен|визволен)[а-яії]* (від|радянськ|червон)/ {year}" for year in (1941, 1943, 1944, 1945)),
    liberated=re.compile(r"звільн|визвол", re.IGNORECASE),
    occupied=re.compile(r"окупова|окупаці|зайнят|захопи|захопл", re.IGNORECASE),
    months=UK_MONTHS,
    # Ukraine within its borders of today, roughly.
    area=(44.3, 52.4, 22.1, 40.3),
    settlements=frozenset({
        "Q21672098",   # village of Ukraine
        "Q4100864",    # urban-type settlement in Ukraine
        "Q121366249",  # rural settlement in Ukraine
        "Q12131624",   # city in Ukraine
        "Q97660032",   # city of oblast significance
    }),
)


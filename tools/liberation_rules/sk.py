"""Slovak: village and town articles that say when the Red Army came ("oslobodená Červenou
armádou", "oslobodili"). Slovakia was an Axis state (the south Hungarian from 1938): its places
were taken, not liberated, and had no occupation; from the Dukla pass in autumn 1944 to April 1945."""

import re

from tools.liberation_articles import ArticleRule
from tools.liberation_rules.cs import SLOVAKIA, dotted_dates
from tools.liberations import inside


def capture_dates(sentence, months):
    """The dotted dates from the first Soviet troops in Slovakia (the Dukla pass, late September
    1944) on: before that the Germans took the towns of the uprising."""
    return [(at, iso) for at, iso in dotted_dates(sentence, months) if iso >= "1944-09-20"]


def _in_slovakia(b):
    """Slovak Wikipedia has Hungarian and Moravian villages too; only Slovakia's count."""
    return b if inside(SLOVAKIA, b.lat, b.lng) else None

SK_MONTHS = {m: i for i, m in enumerate(
    "januára februára marca apríla mája júna júla augusta septembra októbra novembra decembra".split(), 1)}
# A month without a day: "v apríli 1945".
SK_MONTH_FORMS = {m: i for i, m in enumerate(
    "januári februári marci apríli máji júni júli auguste septembri októbri novembri decembri".split(), 1)}

RULE = ArticleRule(
    lang="sk",
    country="Slowakije",
    kamp="sovjet",
    source="sk-articles",
    queries=(
        "oslobodená Červenou armádou 1945", "oslobodená 1945 obec", "oslobodenie obce 1945",
        "oslobodená 1944 obec", "oslobodili 1945 obec", "oslobodené 1945 obec",
        "oslobodenie 1945 mesto", "oslobodená 1945", "oslobodená 1944", "oslobodený 1945",
        "oslobodili 1945", "oslobodili 1944",
    ),
    # Not "sovietsk" alone: Soviet planes bombed many a village before it was taken.
    liberated=re.compile(r"oslobo|Červen[áou]+ armád|vstúpil|obsadil", re.IGNORECASE),
    occupied=None,
    months=SK_MONTHS,
    # Slovakia within its borders of today, roughly.
    area=(47.7, 49.65, 16.8, 22.6),
    first_liberation=1944,
    verb="ingenomen",
    dates=capture_dates,
    settlements=frozenset({"Q6784672"}),  # municipality of Slovakia
    adjust=_in_slovakia,
    month_forms=SK_MONTH_FORMS,
    last_liberation="1945-05-31",
)

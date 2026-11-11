"""Belarusian: village and town articles that say when the place was liberated ("вызвалена ад
нямецка-фашысцкіх захопнікаў", "вызвалены войскамі")."""

import re

from tools.liberation_articles import ArticleRule

BE_MONTHS = {m: i for i, m in enumerate(
    "студзеня лютага сакавіка красавіка мая чэрвеня ліпеня жніўня верасня кастрычніка лістапада снежня".split(), 1)}
BE_MONTHS["траўня"] = 5

def _before_autumn_1944(b):
    """Belarus was free by the end of August 1944: a later date is about something else."""
    return b if b.liberated <= "1944-08-31" else None


# The months without a day ("в марте 1943"): kept apart, known only to the month.
BE_MONTH_FORMS = {m: i for i, m in enumerate(
    "студзені лютым сакавіку красавіку траўні чэрвені ліпені жніўні верасні кастрычніку лістападзе снежні".split(), 1)}


RULE = ArticleRule(
    lang="be",
    country="Sovjet-Unie",
    kamp="sovjet",
    source="be-articles",
    # The bot articles on Smolensk villages ("вызвалена ў 1943 годзе", spelling after ГКНП) give
    # no day, so they are left out of the search.
    queries=tuple(f"insource:/вызвал[а-яіў]*/ {year} -ГКНП" for year in (1943, 1944)),
    # Not "вызваленчы" (of a liberation army) nor a man "вызвалены ад пасады" (relieved of a post).
    # Nor what came "after the liberation" (пасля вызвалення) with a later date.
    liberated=re.compile(r"(?<!пасля )(?<!ад )вызвал(?!енч)(?![а-яіў]* ад пасад)", re.IGNORECASE),
    occupied=re.compile(r"акупава|акупацы|захоплен|захапі|захапл|занят", re.IGNORECASE),
    months=BE_MONTHS,
    # Belarus, with the Smolensk and Bryansk villages Belarusian Wikipedia also has.
    area=(51.2, 56.4, 23.1, 34.5),
    first_liberation=1943,
    # The Soviet annexation of West Belarus in 1939 is no occupation.
    occupation_years=(1941, 1942),
    settlements=frozenset({
        "Q65661087",   # village in Belarus
        "Q1989945",    # agrotown
        "Q91733160",   # urban settlement in Belarus
        "Q79324274",   # city of raion subordinance
        "Q65665664",   # settlement in Belarus (pasiolak)
        "Q22674925",   # former settlement (a village burnt in the war and not rebuilt)
    }),
    adjust=_before_autumn_1944,
    month_forms=BE_MONTH_FORMS,
    last_liberation="1945-05-31",
)

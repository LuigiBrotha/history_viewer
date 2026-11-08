"""Add what the stored articles say about each Veldslag to battles.json: its Landen,
Bevelhebbers and Eenheden.

Reads the wikitext kept in the database by the extractions, so it never touches a dump:

    poetry run python -m tools.enrich_battles [--battles FILE] [--database URL]
"""

import argparse
import json
import re
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import BattleArticle, ForeignBattleArticle
from tools.battle_winner import COMMENT, REF
from tools.countries import land_of, side_countries
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_OUTPUT, _write_atomically, find_infobox
from tools.wiki_languages import LANGUAGES, ORDER

ENGLISH_SIDES = ("combatant1", "combatant2", "combatant3")
PEOPLE_FIELDS = {"en": ("commander1", "commander2", "commander3"), "nl": ("commander1", "commander2"),
                 "de": ("befehlshaber1", "befehlshaber2"), "pl": ("dowódca1", "dowódca2"),
                 "ru": ("командир1", "командир2", "командир3"), "fr": ("commandant1", "commandant2", "commandant3"),
                 "it": ("comandante1", "comandante2", "comandante3"), "ja": ("commander1", "commander2", "commander3")}
UNIT_FIELDS = {"en": ("units1", "units2", "units3"), "nl": ("units1", "units2"), "fr": ("unités1", "unités2"),
               "ja": ("units1", "units2")}
_LINK = re.compile(r"\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def _fields(lang, wikitext):
    if lang == "en":
        return find_infobox(wikitext) or {}
    return find_infobox(wikitext, LANGUAGES[lang].infobox) or {}


def linked_names(field):
    """The titles of the articles a field links to, each once; files, categories and countries left out."""
    names = []
    for target in _LINK.findall(COMMENT.sub("", REF.sub("", field or ""))):
        title = re.sub(r"[\s_]+", " ", target).strip()
        if not title or ":" in title or land_of(title):
            continue
        title = title[:1].upper() + title[1:]
        if title not in names:
            names.append(title)
    return names


# Ranks are linked next to a commander's name; they are not Bevelhebbers.
RANKS = {
    "admiral", "vice admiral", "rear admiral", "fleet admiral", "grand admiral", "commodore", "captain", "commander",
    "general", "lieutenant general", "major general", "brigadier", "brigadier general", "colonel", "lieutenant colonel",
    "major", "lieutenant", "field marshal", "marshal", "marshal of the soviet union", "general of the army",
    "generalfeldmarschall", "generaloberst", "generalleutnant", "generalmajor", "oberst", "hauptmann", "leutnant",
    "großadmiral", "grossadmiral", "vizeadmiral", "konteradmiral", "kapitän zur see", "fregattenkapitän",
    "korvettenkapitän", "kapitänleutnant", "oberleutnant zur see", "taisa", "chūjō", "taishō", "shōshō",
}
# A name like this in a commander field is an Eenheid, not a person.
UNIT_NAME = re.compile(
    r"\b(?:front|army|armies|corps|division|fleet|group|brigade|regiment|squadron|flotilla|battalion|wing|"
    r"command|stavka|okh|okw|kriegsmarine|luftwaffe|wehrmacht)\b",
    re.IGNORECASE,
)


def _is_rank(name):
    return re.sub(r"\s*\([^)]*\)", "", name).strip().lower() in RANKS or "(rank)" in name.lower()


def people_and_units(lang, wikitext):
    """(Bevelhebbers, Eenheden) linked from an article's infobox. Ranks are left out, and
    units named in a commander field count as Eenheden."""
    fields = _fields(lang, wikitext)
    people, units = [], []
    for key in PEOPLE_FIELDS.get(lang, ()):
        for name in linked_names(fields.get(key, "")):
            if _is_rank(name):
                continue
            target = units if UNIT_NAME.search(re.sub(r"\([^)]*\)", "", name)) else people
            if name not in target:
                target.append(name)
    for key in UNIT_FIELDS.get(lang, ()):
        for name in linked_names(fields.get(key, "")):
            if name not in units:
                units.append(name)
    return people, units


def countries_of(lang, wikitext):
    """The Landen on all sides of an article's infobox, in order, each once."""
    fields = _fields(lang, wikitext)
    if lang == "en":
        sides = ENGLISH_SIDES
    else:
        language = LANGUAGES[lang]
        sides = (language.side1, language.side2)
    found = []
    for side in sides:
        for land in side_countries(lang, fields.get(side, "")):
            if land not in found:
                found.append(land)
    return found


DEFAULT_NAMES_DIR = Path("~/.cache/uboats/wikipedia/other")
DEFAULT_UNIT_BATTLES = Path("~/.cache/uboats/wikipedia/unit_battles.json")


def _unit_battles(path):
    """The result of tools.extract_unit_battles, or empty tables when it is missing."""
    path = Path(path).expanduser()
    if not path.exists():
        return {"units": {}, "people": {}, "aliases": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def run(battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE, unit_battles=DEFAULT_UNIT_BATTLES,
        names_dir=DEFAULT_NAMES_DIR):
    from tools.english_names import read_names

    battles_path = Path(battles_path)
    # A Bevelhebber or Eenheid linked in another language goes by its English article's title,
    # so that "Жуков, Георгий Константинович" and "Georgy Zhukov" are one label.
    english_names = read_names(names_dir)
    known = _unit_battles(unit_battles)
    # Only the other names of units and people (Rommel → Erwin Rommel); the Veldslagen their own
    # articles name do not count, only who the infobox of the Veldslag itself names (user's choice).
    aliases = known.get("aliases", {})
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    engine = create_engine(database_url)
    with Session(engine) as session:
        english = dict(session.execute(select(BattleArticle.title, BattleArticle.wikitext)).all())
        # The foreign articles of each Veldslag, in the order of the languages.
        foreign = {}
        for lang, title, battle, wikitext in session.execute(
            select(ForeignBattleArticle.lang, ForeignBattleArticle.title, ForeignBattleArticle.battle,
                   ForeignBattleArticle.wikitext)
        ).all():
            foreign.setdefault(battle or title, []).append((lang, wikitext))
    engine.dispose()
    for articles in foreign.values():
        articles.sort(key=lambda item: ORDER.index(item[0]) if item[0] in ORDER else len(ORDER))
    for battle in battles:
        title = battle["title"]
        sources = []
        if battle.get("lang", "en") == "en" and title in english:
            sources.append(("en", english[title]))
        sources += foreign.get(title, [])
        # Each field from the first article that has it: English, then the others in order.
        battle["countries"] = next((c for lang, text in sources if (c := countries_of(lang, text))), [])
        found = []
        for lang, text in sources:
            people, units = people_and_units(lang, text)
            table = english_names.get(lang, {})
            found.append(([table.get(n, n) for n in people], [table.get(n, n) for n in units]))
        people = [aliases.get(n, n) for n in next((people for people, _ in found if people), [])]
        units = [aliases.get(n, n) for n in next((units for _, units in found if units), [])]
        battle["commanders"] = list(dict.fromkeys(people))
        battle["units"] = list(dict.fromkeys(units))
    _write_atomically(battles_path, json.dumps(battles, ensure_ascii=False, separators=(",", ":")))
    print(f"{sum(1 for b in battles if b['countries'])} of {len(battles)} Veldslagen have Landen")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to enrich")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the stored articles (an SQLite URL)")
    parser.add_argument("--unit-battles", default=DEFAULT_UNIT_BATTLES, help="the result of tools.extract_unit_battles")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.database, arguments.unit_battles)


if __name__ == "__main__":
    main()

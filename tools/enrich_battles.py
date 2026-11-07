"""Add what the stored articles say about each Veldslag to battles.json: its Landen.

Reads the wikitext kept in the database by the extractions, so it never touches a dump:

    poetry run python -m tools.enrich_battles [--battles FILE] [--database URL]
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import BattleArticle, ForeignBattleArticle
from tools.countries import side_countries
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_OUTPUT, _write_atomically, find_infobox
from tools.wiki_languages import LANGUAGES, ORDER

ENGLISH_SIDES = ("combatant1", "combatant2", "combatant3")


def countries_of(lang, wikitext):
    """The Landen on all sides of an article's infobox, in order, each once."""
    if lang == "en":
        fields = find_infobox(wikitext) or {}
        sides = ENGLISH_SIDES
    else:
        language = LANGUAGES[lang]
        fields = find_infobox(wikitext, language.infobox) or {}
        sides = (language.side1, language.side2)
    found = []
    for side in sides:
        for land in side_countries(lang, fields.get(side, "")):
            if land not in found:
                found.append(land)
    return found


def run(battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE):
    battles_path = Path(battles_path)
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
        countries = []
        for lang, wikitext in sources:
            countries = countries_of(lang, wikitext)
            if countries:
                break
        battle["countries"] = countries
    _write_atomically(battles_path, json.dumps(battles, ensure_ascii=False, separators=(",", ":")))
    print(f"{sum(1 for b in battles if b['countries'])} of {len(battles)} Veldslagen have Landen")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to enrich")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the stored articles (an SQLite URL)")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.database)


if __name__ == "__main__":
    main()

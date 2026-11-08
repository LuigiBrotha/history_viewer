"""The Dutch version of every Artikel, made ahead so that the NL button need not wait.

    poetry run python -m tools.dutch_articles [--battles FILE] [--database URL] [--dir DIR]

1. The Dutch Wikipedia's article about the same battle, found through the language links of the
   Dutch dump (a Dutch page linking to the original), is stored as it is. One the dump scans
   already stored for the Veldslag is used as it is; the others are fetched from the Wikipedia
   API, 50 at a time.
2. Every other Artikel whose language has an Argos model is translated (through English) and
   stored, language by language, so that each model is loaded once. What is stored is skipped,
   so a stopped run goes on where it was.
"""

import argparse
import asyncio
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import DutchArticle, ForeignBattleArticle
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_OUTPUT
from tools.fill_battle_articles import titles_for_ids
from tools.merge_languages import _ROW, _unescape

DEFAULT_DIR = Path("~/.cache/uboats/wikipedia/other")


def _key(title):
    return title.replace("_", " ")


def dutch_counterparts(langlinks_lines, wanted):
    """{(lang, title): Dutch page id} of the wanted articles a Dutch page links to."""
    found = {}
    for line in langlinks_lines:
        for page_id, lang, title in _ROW.findall(line):
            key = (lang, _key(_unescape(title)))
            if key in wanted and key not in found:
                found[key] = int(page_id)
    return found


def originals(battles):
    """(lang, title) of the Artikel of each Veldslag that is not Dutch itself."""
    return [(b.get("lang", "en"), b["title"]) for b in battles if b.get("lang", "en") != "nl"]


def find_dutch(battles, database_url, directory, fetch=None):
    """Step 1: stores the Dutch Wikipedia's articles. Returns how many were stored."""
    from tools.wikidata_battles import fetch_wikitexts

    directory = Path(directory).expanduser()
    wanted = set(originals(battles))
    engine = create_engine(database_url)
    DutchArticle.__table__.create(engine, checkfirst=True)
    with Session(engine) as session:
        done = set(session.execute(select(DutchArticle.lang, DutchArticle.title)).all())
        # Dutch articles the dump scans stored for a Veldslag of another language.
        scanned = {row.battle: row for row in session.scalars(select(ForeignBattleArticle).where(
            ForeignBattleArticle.lang == "nl", ForeignBattleArticle.battle.is_not(None)))}
    by_battle = {b["title"]: (b.get("lang", "en"), b["title"]) for b in battles}
    stored = {}
    for battle, row in scanned.items():
        key = by_battle.get(battle)
        if key and key in wanted and key[0] != "nl" and key not in done:
            stored[key] = (row.title, row.wikitext)
    langlinks = sorted(directory.glob("nlwiki-*-langlinks.sql.gz"))
    index = sorted(directory.glob("nlwiki-*-pages-articles-multistream-index.txt.bz2"))
    if langlinks and index:
        rest = wanted - done - set(stored)
        with gzip.open(langlinks[-1], "rt", encoding="utf-8", errors="replace") as lines:
            pages = dutch_counterparts(lines, rest)
        titles = titles_for_ids(index[-1], set(pages.values()))
        dutch_titles = {key: titles[page] for key, page in pages.items() if page in titles}
        print(f"Dutch articles: {len(stored)} stored by the scans, {len(dutch_titles)} to fetch", file=sys.stderr,
              flush=True)
        texts = fetch_wikitexts([("nl", t) for t in set(dutch_titles.values())], **({"fetch": fetch} if fetch else {}))
        for key, nl_title in dutch_titles.items():
            if ("nl", nl_title) in texts:
                stored[key] = (nl_title, texts[("nl", nl_title)])
    now = datetime.now(timezone.utc)
    with Session(engine) as session, session.begin():
        for (lang, title), (nl_title, wikitext) in stored.items():
            session.merge(DutchArticle(lang=lang, title=title, kind="wikipedia", nl_title=nl_title, content=wikitext,
                                       made_at=now))
    engine.dispose()
    return len(stored)


async def translate_rest(battles, database_url):
    """Step 2: translates every Artikel without a Dutch version whose language has a model."""
    from app.services.storage.database import create_engine as create_async, create_session_factory
    from app.services.wiki.article_service import ArticleService

    engine = create_async(database_url.replace("sqlite://", "sqlite+aiosqlite://", 1))
    factory = create_session_factory(engine)
    service = ArticleService(factory)
    async with factory() as session:
        done = set((await session.execute(select(DutchArticle.lang, DutchArticle.title))).all())
    todo = [key for key in originals(battles) if key not in done and service.models.can_reach_dutch(key[0])]
    todo.sort(key=lambda key: (key[0] != "en", key[0]))
    made = 0
    for number, (lang, title) in enumerate(todo, 1):
        try:
            if await service.dutch(title, lang) is not None:
                made += 1
        except Exception as error:  # one bad article does not stop the rest
            print(f"{lang}:{title}: {error!r}", file=sys.stderr, flush=True)
        if number % 25 == 0:
            print(f"translated {number} of {len(todo)}", file=sys.stderr, flush=True)
    await engine.dispose()
    return made


def run(battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE, directory=DEFAULT_DIR):
    battles = json.loads(Path(battles_path).read_text(encoding="utf-8"))
    found = find_dutch(battles, database_url, directory)
    made = asyncio.run(translate_rest(battles, database_url))
    print(f"Dutch versions: {found} from the Dutch Wikipedia, {made} translated")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="battles.json, whose Artikelen get a Dutch version")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the articles (an SQLite URL)")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="directory with the Dutch dump's langlinks and index")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.database, arguments.dir)


if __name__ == "__main__":
    main()

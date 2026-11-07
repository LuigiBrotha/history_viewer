"""Add the Veldslagen of the Dutch, German and Polish Wikipedia to battles.json.

Each language's multistream dump is streamed once (memory stays small) and its battles are
kept in `<lang>wiki-battles.json` next to the dump, so a later run only merges again. Then
the language links decide which articles are the same battle (see tools.merge_languages):

    poetry run python -m tools.extract_other_languages [--dir DIR] [--battles FILE] [--database URL] [--rescan]
"""

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, delete, update
from sqlalchemy.orm import Session

from app.services.storage.models import ForeignBattleArticle
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_OUTPUT, _write_atomically, iter_raw_pages
from tools.merge_languages import merge_languages, read_langlinks
from tools.wiki_languages import LANGUAGES, ORDER, extract_other_battle

DEFAULT_DIR = Path("~/.cache/uboats/wikipedia/other")
SAVE_EVERY_SECONDS = 60
PROGRESS_EVERY = 100_000


def _latest(directory, pattern):
    candidates = sorted(directory.glob(pattern))
    return candidates[-1] if candidates else None


def _candidate_pages(dump, language, skip_pages=0):
    """(page number, page id, title, wikitext) of the article pages with this language's infobox."""
    for number, raw in enumerate(iter_raw_pages(dump), 1):
        if number <= skip_pages:
            continue
        if b"<redirect" in raw or language.candidate.search(raw) is None:
            yield number, None, None, None
            continue
        page = ET.fromstring(raw[raw.rfind(b"<page>"):] + b"</page>")
        if page.findtext("ns") != "0" or not page.findtext("title"):
            yield number, None, None, None
            continue
        yield number, int(page.findtext("id")), page.findtext("title"), page.findtext("revision/text") or ""


def scan(lang, dump, out_path, engine, save_every_seconds=SAVE_EVERY_SECONDS):
    """Stream one dump into `out_path` ({"complete", "pages", "battles": [{"id", "record"}]}),
    storing each battle's wikitext. A stopped scan continues where it was."""
    language = LANGUAGES[lang]
    state = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"complete": False, "pages": 0, "battles": []}
    battles = {item["record"]["title"]: item for item in state["battles"]}
    pages = state["pages"]
    # Articles wait here and are written in one short transaction per save, so other writers
    # (the server, the ship crawl) never find the database locked for long.
    articles = []

    def save(complete=False):
        if articles:
            with Session(engine) as session, session.begin():
                for article in articles:
                    session.merge(article)
            articles.clear()
        _write_atomically(out_path, json.dumps({"complete": complete, "pages": pages,
                                                 "battles": list(battles.values())}, ensure_ascii=False))

    last_save = time.monotonic()
    for pages, page_id, title, wikitext in _candidate_pages(dump, language, skip_pages=pages):
        if title is not None:
            record, _ = extract_other_battle(lang, title, wikitext)
            if record is not None:
                battles[title] = {"id": page_id, "record": record}
                articles.append(ForeignBattleArticle(lang=lang, title=title, wikitext=wikitext, dump_name=dump.name,
                                                     extracted_at=datetime.now(timezone.utc)))
        if time.monotonic() - last_save >= save_every_seconds:
            save()
            last_save = time.monotonic()
        if pages % PROGRESS_EVERY == 0:
            print(f"{lang}: {pages} pages read, {len(battles)} battles", file=sys.stderr, flush=True)
    save()
    with Session(engine) as session, session.begin():
        session.execute(delete(ForeignBattleArticle).where(ForeignBattleArticle.lang == lang,
                                                           ForeignBattleArticle.title.not_in(list(battles))))
    save(complete=True)
    return state


def run(directory=DEFAULT_DIR, battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE, languages=ORDER, rescan=False):
    directory = Path(directory).expanduser()
    battles_path = Path(battles_path)
    engine = create_engine(database_url)
    ForeignBattleArticle.__table__.create(engine, checkfirst=True)
    others, links = {}, {}
    for lang in languages:
        dump = _latest(directory, f"{lang}wiki-*-pages-articles-multistream.xml.bz2")
        out_path = directory / f"{lang}wiki-battles.json"
        if rescan and out_path.exists():
            out_path.unlink()
        state = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else None
        if state is None or not state["complete"]:
            if dump is None:
                print(f"{lang}: no dump in {directory}, skipped")
                continue
            print(f"{lang}: reading {dump.name}…", file=sys.stderr, flush=True)
            scan(lang, dump, out_path, engine)
            state = json.loads(out_path.read_text(encoding="utf-8"))
        items = state["battles"]
        others[lang] = [item["record"] for item in items]
        langlinks_path = _latest(directory, f"{lang}wiki-*-langlinks.sql.gz")
        if langlinks_path is not None:
            by_id = read_langlinks(langlinks_path, {item["id"] for item in items}, {"en", *ORDER})
            for item in items:
                links[(lang, item["record"]["title"])] = by_id.get(item["id"], {})
        print(f"{lang}: {len(items)} battles")
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    owners = {}
    merged = merge_languages(battles, others, links, owners)
    with Session(engine) as session, session.begin():
        session.execute(update(ForeignBattleArticle).values(battle=None))
        for (lang, title), battle in owners.items():
            session.execute(update(ForeignBattleArticle)
                            .where(ForeignBattleArticle.lang == lang, ForeignBattleArticle.title == title)
                            .values(battle=battle))
    engine.dispose()
    _write_atomically(battles_path, json.dumps(merged, ensure_ascii=False, separators=(",", ":")))
    new = sum(1 for b in merged if b.get("lang", "en") != "en")
    filled = sum(1 for b in merged if b.get("filled"))
    print(f"{len(merged)} Veldslagen: {new} new from other languages, {filled} English ones filled in")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dir", default=DEFAULT_DIR, help="directory with the nl/de/pl dumps and langlinks")
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to merge into")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database that receives the articles (an SQLite URL)")
    parser.add_argument("--rescan", action="store_true", help="read every dump again instead of reusing earlier scans")
    arguments = parser.parse_args(argv)
    run(arguments.dir, arguments.battles, arguments.database, rescan=arguments.rescan)


if __name__ == "__main__":
    main()

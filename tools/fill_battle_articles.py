"""Fill the Artikelen and Winnaars of the known Veldslagen straight from the multistream dump.

Only the bz2 streams that hold a Veldslag are decompressed, and the index and redirect files
are read line by line keeping only the wanted rows, so memory stays small.
"""

import argparse
import bz2
import gzip
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.services.storage.models import BattleArticle, BattleRedirect
from tools.battle_winner import winner
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_DUMP, DEFAULT_OUTPUT, _write_atomically, find_infobox

READ_SIZE = 1 << 20
COMMIT_EVERY = 100
_SQL_ROW = re.compile(
    r"\((\d+),(-?\d+),'((?:[^'\\]|\\.)*)',(?:'(?:[^'\\]|\\.)*'|NULL),(?:'(?:[^'\\]|\\.)*'|NULL)\)"
)
_SQL_ESCAPE = re.compile(r"\\(.)")
_SQL_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0"}
# Redirect pages outside the article namespace, recognised by their title prefix.
_OTHER_NAMESPACES = {
    "talk", "user", "user talk", "wikipedia", "wikipedia talk", "file", "file talk", "mediawiki",
    "template", "template talk", "help", "category", "category talk", "portal", "portal talk",
    "draft", "draft talk", "module", "module talk", "timedtext", "wp", "wt",
}


def _index_rows(index_path):
    with bz2.open(index_path, "rt", encoding="utf-8") as lines:
        for line in lines:
            offset, page_id, title = line.rstrip("\n").split(":", 2)
            yield int(offset), int(page_id), html.unescape(title)


def stream_offsets(index_path, titles):
    """Title → offset of the bz2 stream holding it, for the wanted titles only."""
    return {title: offset for offset, _, title in _index_rows(index_path) if title in titles}


def titles_for_ids(index_path, ids):
    """Page id → title, for the wanted page ids only."""
    return {page_id: title for _, page_id, title in _index_rows(index_path) if page_id in ids}


def _read_stream(dump, offset):
    dump.seek(offset)
    decompressor = bz2.BZ2Decompressor()
    pieces = []
    while not decompressor.eof:
        chunk = dump.read(READ_SIZE)
        if not chunk:
            break
        pieces.append(decompressor.decompress(chunk))
    return b"".join(pieces)


def read_pages(dump_path, offsets):
    """(title, wikitext) of every article-namespace page in the streams at these offsets."""
    with open(dump_path, "rb") as dump:
        for offset in sorted(set(offsets)):
            root = ET.fromstring(b"<pages>" + _read_stream(dump, offset) + b"</pages>")
            for page in root.iter("page"):
                if page.findtext("ns") == "0" and page.find("redirect") is None:
                    yield page.findtext("title"), page.findtext("revision/text") or ""


def _unescape(value):
    return _SQL_ESCAPE.sub(lambda m: _SQL_ESCAPES.get(m.group(1), m.group(1)), value)


def redirects_to(sql_gz_path, targets):
    """Redirect page id → target title, for article-namespace redirects to one of the targets."""
    found = {}
    with gzip.open(sql_gz_path, "rt", encoding="utf-8", errors="replace") as lines:
        for line in lines:  # one INSERT per line, or one row per line, depending on the dump
            for page_id, namespace, title in _SQL_ROW.findall(line):
                if namespace == "0":
                    target = _unescape(title).replace("_", " ")
                    if target in targets:
                        found[int(page_id)] = target
    return found


def _latest(directory, pattern):
    candidates = sorted(Path(directory).expanduser().glob(pattern))
    if not candidates:
        raise SystemExit(f"No {pattern} found in {directory}")
    return candidates[-1]


def _is_article_title(title):
    prefix, colon, _ = title.partition(":")
    return not colon or prefix.strip().lower() not in _OTHER_NAMESPACES


def run(directory, database_url=DEFAULT_DATABASE, battles_path=DEFAULT_OUTPUT):
    directory = Path(directory).expanduser()
    dump_path = _latest(directory, "*-pages-articles-multistream.xml.bz2")
    index_path = _latest(directory, "*-pages-articles-multistream-index.txt.bz2")
    redirect_path = _latest(directory, "*-redirect.sql.gz")
    battles_path = Path(battles_path)
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    titles = {battle["title"] for battle in battles}

    print("Reading the index…", file=sys.stderr, flush=True)
    offsets = stream_offsets(index_path, titles)

    engine = create_engine(database_url)
    BattleArticle.__table__.create(engine, checkfirst=True)
    BattleRedirect.__table__.create(engine, checkfirst=True)
    winners = {}
    print(f"Reading {len(set(offsets.values()))} streams…", file=sys.stderr, flush=True)
    with Session(engine) as session:
        for title, wikitext in read_pages(dump_path, offsets.values()):
            if title not in titles or title in winners:
                continue
            winners[title] = winner(find_infobox(wikitext) or {})
            session.merge(BattleArticle(title=title, wikitext=wikitext, dump_name=dump_path.name,
                                        extracted_at=datetime.now(timezone.utc)))
            if len(winners) % COMMIT_EVERY == 0:
                session.commit()
                print(f"  {len(winners)} articles", file=sys.stderr, flush=True)
        session.commit()

    print("Reading the redirects…", file=sys.stderr, flush=True)
    targets = redirects_to(redirect_path, set(winners))
    aliases = titles_for_ids(index_path, set(targets))
    pairs = {alias: targets[page_id] for page_id, alias in aliases.items()
             if _is_article_title(alias) and alias not in titles}

    with Session(engine) as session, session.begin():
        session.execute(delete(BattleRedirect))
        stale = set(session.scalars(select(BattleArticle.title))) - titles
        if stale:
            session.execute(delete(BattleArticle).where(BattleArticle.title.in_(stale)))
        session.add_all(BattleRedirect(alias=alias, title=title) for alias, title in sorted(pairs.items()))
    engine.dispose()

    for battle in battles:
        battle["winner"] = winners.get(battle["title"], battle.get("winner", []))
    _write_atomically(battles_path, json.dumps(battles, ensure_ascii=False, separators=(",", ":")))

    missing = sorted(titles - set(winners))
    print(f"{len(winners)} articles found, {len(pairs)} redirects, {len(missing)} titles missing")
    for title in missing:
        print(f"  missing: {title}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dir", default=DEFAULT_DUMP, help="directory with the multistream dump, its index and redirect.sql.gz")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database that receives the articles (an SQLite URL)")
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to add winners to")
    arguments = parser.parse_args(argv)
    run(arguments.dir, arguments.database, arguments.battles)


if __name__ == "__main__":
    main()

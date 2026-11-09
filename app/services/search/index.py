"""The search index: every text of every Onderwerp, in a SQLite file of its own.

Built by tools.build_search_index, next to the database, and replaced in one step, so the app
reads either the old index or the new one. Word by word (FTS5), with beside it the list of
words that occur in more than one text, in which a mistyped word finds what it was meant to be.
The texts themselves are not stored in it: they are in the database already.
"""

import html
import os
import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

from sqlalchemy.engine import make_url

INDEX_NAME = "search_index.db"
Document = tuple[str, str, str, str]  # kind, key, title, text

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_REFERENCE = re.compile(r"<ref\b[^>/]*(?:/>|>.*?</ref>)", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_PIPED_LINK = re.compile(r"\[\[[^\[\]|]*\|([^\[\]]*)\]\]")
_MARKUP = re.compile(r"''+|[\[\]{}|=*#]+")
_SPACE = re.compile(r"\s+")


def index_path(database_url: str) -> Path:
    """Where the index of this database lies: beside it, also when that is a symbolic link."""
    return Path(make_url(database_url).database).resolve().with_name(INDEX_NAME)


def plain_text(text: str) -> str:
    """The words of wikitext or HTML. Infoboxes stay: their names are worth finding."""
    text = _REFERENCE.sub(" ", _COMMENT.sub(" ", text))
    text = _PIPED_LINK.sub(r"\1", _TAG.sub(" ", text))
    return _SPACE.sub(" ", html.unescape(_MARKUP.sub(" ", text))).strip()


def _texts(*parts: Iterable[str | None]) -> str:
    return " ".join(part for part in parts if part)


def _one(source: sqlite3.Connection, query: str, *key: str) -> str | None:
    row = source.execute(query, key).fetchone()
    return row[0] if row else None


def battle_documents(source: sqlite3.Connection, battles: list[dict]) -> Iterator[Document]:
    """A document per text of a Veldslag: its article in each language and each Dutch version."""
    linked = defaultdict(list)
    for lang, title, battle in source.execute(
        "SELECT lang, title, battle FROM foreign_battle_articles WHERE battle IS NOT NULL"
    ):
        linked[battle].append((lang, title))
    for battle in battles:
        title, english = battle["title"], battle.get("title_en")
        articles = {(battle.get("lang", "en"), title), *linked[title]}
        if english:
            articles |= {("en", english), *linked[english]}
        heading = _texts(title, english, battle.get("place"))
        for lang, name in sorted(articles):
            original = (
                _one(source, "SELECT wikitext FROM battle_articles WHERE title = ?", name)
                if lang == "en"
                else _one(source, "SELECT wikitext FROM foreign_battle_articles WHERE lang = ? AND title = ?", lang, name)
            )
            dutch = _one(source, "SELECT content FROM dutch_articles WHERE lang = ? AND title = ?", lang, name)
            for text in (original, dutch):
                if text:
                    yield "battle", title, heading, plain_text(text)


def boat_documents(source: sqlite3.Connection) -> Iterator[Document]:
    patrols = defaultdict(list)
    for boat_id, commander, description in source.execute("SELECT boat_id, commander, description FROM patrols"):
        patrols[boat_id].extend((commander, description))
    for boat_id, slug, number, kind, builder, fate in source.execute(
        "SELECT id, slug, number, type, builder, fate FROM boats"
    ):
        yield "boat", slug, _texts(number, kind), _texts(builder, fate, *patrols[boat_id])


def ship_documents(source: sqlite3.Connection) -> Iterator[Document]:
    details = {
        row[0]: row[1:]
        for row in source.execute(
            "SELECT ship_external_id, ship_type, owner, homeport, fate, convoy, route, cargo, history, notes FROM ship_details"
        )
    }
    seen = set()
    for ship, name in source.execute("SELECT ship_external_id, name FROM ship_hits ORDER BY date"):
        if ship not in seen:
            seen.add(ship)
            yield "ship", ship, name, _texts(*details.get(ship, ()))


def build_index(database: Path, battles: list[dict], output: Path) -> int:
    """Writes the index and returns how many documents went in."""
    partial = output.with_suffix(".partial")
    partial.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    index = sqlite3.connect(partial)
    try:
        index.execute(
            "CREATE VIRTUAL TABLE search USING fts5(title, body, content='', "
            "tokenize='unicode61 remove_diacritics 2')"
        )
        index.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, kind TEXT, key TEXT)")
        count = 0
        for documents in (battle_documents(source, battles), boat_documents(source), ship_documents(source)):
            for kind, key, title, text in documents:
                count += 1
                index.execute("INSERT INTO documents VALUES (?, ?, ?)", (count, kind, key))
                index.execute("INSERT INTO search(rowid, title, body) VALUES (?, ?, ?)", (count, title, text))
        index.execute("INSERT INTO search(search) VALUES ('optimize')")
        index.execute("CREATE VIRTUAL TABLE vocabulary USING fts5vocab(search, row)")
        index.execute("CREATE TABLE terms (term TEXT PRIMARY KEY, first TEXT, size INTEGER, docs INTEGER) WITHOUT ROWID")
        index.execute(
            "INSERT INTO terms SELECT term, substr(term, 1, 1), length(term), doc FROM vocabulary "
            "WHERE doc >= 2 AND length(term) >= 3"
        )
        index.execute("CREATE INDEX terms_near ON terms (first, size)")
        index.execute("DROP TABLE vocabulary")
        index.commit()
    finally:
        index.close()
        source.close()
    os.replace(partial, output)
    return count

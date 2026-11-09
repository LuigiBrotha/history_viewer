import asyncio
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from wireup import injectable

from app.core.config import settings
from app.services.search.index import index_path

MIN_LENGTH = 3
MAX_LIKE_TERMS = 12
MAX_ROWS = 20000
# How much a word in a title counts against one in the text (title, body).
RANK = "bm25(search, 10.0, 1.0)"
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class SearchOut:
    """The keys of each kind of Onderwerp found, best first."""

    available: bool = True
    battles: list[str] = field(default_factory=list)
    boats: list[str] = field(default_factory=list)
    ships: list[str] = field(default_factory=list)


def words_of(query: str) -> list[str]:
    """The words of a query the way the index holds them: lower case, without accents."""
    decomposed = unicodedata.normalize("NFKD", query.lower())
    return _WORD.findall("".join(char for char in decomposed if not unicodedata.combining(char)))


def allowed_typos(word: str) -> int:
    if len(word) < 4:
        return 0
    return 1 if len(word) <= 7 else 2


def typos_between(a: str, b: str, limit: int) -> int:
    """How many edits apart two words are, a swap of neighbours counting as one; above limit, limit + 1."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    before, row = None, list(range(len(b) + 1))
    for i, char in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            cost = min(row[j] + 1, current[j - 1] + 1, row[j - 1] + (char != other))
            if before is not None and i > 1 and j > 1 and char == b[j - 2] and a[i - 2] == other:
                cost = min(cost, before[j - 2] + 1)
            current.append(cost)
        if min(current) > limit:
            return limit + 1
        before, row = row, current
    return row[-1]


def _like_terms(index: sqlite3.Connection, word: str) -> list[str]:
    """Words in the index a typing error away from this one, nearest and commonest first. The
    first letter is taken to be right."""
    limit = allowed_typos(word)
    if limit == 0:
        return []
    found = []
    for term, docs in index.execute(
        "SELECT term, docs FROM terms WHERE first = ? AND size BETWEEN ? AND ?",
        (word[0], len(word) - limit, len(word) + limit),
    ):
        typos = typos_between(word, term, limit)
        if 0 < typos <= limit:
            found.append((typos, -docs, term))
    return [term for _, _, term in sorted(found)[:MAX_LIKE_TERMS]]


def _quoted(word: str) -> str:
    return '"' + word.replace('"', '""') + '"'


def match_expression(index: sqlite3.Connection, words: list[str]) -> str:
    """Every word must be there, or one like it; the last may still be being typed."""
    parts = []
    for position, word in enumerate(words, 1):
        options = [_quoted(word), *(_quoted(term) for term in _like_terms(index, word))]
        if position == len(words):
            options.append(_quoted(word) + "*")
        parts.append("(" + " OR ".join(options) + ")")
    return " AND ".join(parts)


@injectable
class SearchService:
    """Search through the text of every Onderwerp. Reads the index file as it is on each query."""

    def __init__(self, path: Path | None = None):
        self._path = path if path is not None else index_path(settings.DATABASE_URL)

    async def search(self, query: str) -> SearchOut:
        return await asyncio.to_thread(self._search, query)

    def _search(self, query: str) -> SearchOut:
        if not self._path.exists():
            return SearchOut(available=False)
        words = words_of(query)
        if sum(map(len, words)) < MIN_LENGTH:
            return SearchOut()
        index = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        try:
            rows = index.execute(
                f"SELECT kind, key FROM search JOIN documents ON id = search.rowid "
                f"WHERE search MATCH ? ORDER BY {RANK} LIMIT ?",
                (match_expression(index, words), MAX_ROWS),
            ).fetchall()
        finally:
            index.close()
        # An Onderwerp can have many texts: its place is that of the best one.
        found: dict[str, dict[str, None]] = {"battle": {}, "boat": {}, "ship": {}}
        for kind, key in rows:
            found[kind].setdefault(key)
        return SearchOut(battles=list(found["battle"]), boats=list(found["boat"]), ships=list(found["ship"]))

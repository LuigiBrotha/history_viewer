import json
from pathlib import Path

from app.core.config import FRONTEND_DIR

BATTLES_FILE = FRONTEND_DIR / "battles" / "battles.json"

# path -> (mtime_ns, titles)
_cache: dict[Path, tuple[int, frozenset[str]]] = {}


def known_battle_titles(path: Path = BATTLES_FILE) -> frozenset[str]:
    """The titles in battles.json, re-read only when the file's modification time changes."""
    mtime = path.stat().st_mtime_ns
    cached = _cache.get(path)
    if cached is None or cached[0] != mtime:
        titles = frozenset(battle["title"] for battle in json.loads(path.read_text(encoding="utf-8")))
        cached = _cache[path] = (mtime, titles)
    return cached[1]

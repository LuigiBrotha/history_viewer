"""Plaatshints: the places the articles of a Veldslag name, with their coordinates.

For every Veldslag, from its English article and its articles in other languages:
- the places linked in the infobox's place field (kind "infobox");
- the places linked in the text (kind "artikel");
- place names in the text without a link (kind "artikel"). A name often fits several places
  ("Alexandria"); the one nearest the linked places of the same battle is taken, at most
  MAX_DISTANCE_KM away. Without linked places only a name with one place counts.

Coordinates come from each Wikipedia's geo_tags table (the primary position of each page) and
its index; redirects are followed for links. Countries and events (the battles themselves) are
no places. Per language a scratch SQLite file holds the places while the hints are made, so
memory stays small. The hints are stored per Veldslag in the table battle_hints:

    poetry run python -m tools.place_hints [--battles FILE] [--database URL]
"""

import argparse
import gzip
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.services.storage.models import BattleArticle, BattleHints, ForeignBattleArticle
from tools.countries import land_of
from tools.extract_battles import DEFAULT_DATABASE, DEFAULT_OUTPUT, INFOBOX, find_infobox, strip_comments
from tools.fill_battle_articles import _SQL_ROW, _index_rows, _unescape
from tools.wiki_languages import LANGUAGES

ENGLISH_DIR = Path("~/.cache/uboats/wikipedia")
OTHER_DIR = Path("~/.cache/uboats/wikipedia/other")
MAX_DISTANCE_KM = 1000
MAX_HINTS = 200
# geo_tags types that are no place to fight at, for any hint.
NOT_PLACES = {"country", "event"}
# The types a name without a link may stand for (None: the page did not say).
NAMED_TYPES = {None, "city", "isle", "mountain", "pass", "waterbody", "river", "adm2nd", "adm3rd"}
# Languages whose names start with a capital, so that unlinked names can be found.
CAPITALISED = {"en", "nl", "de", "pl", "ru", "fr", "it"}
_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_GEO_ROW = re.compile(r"\((\d+),(\d+),'earth',1,(-?[\d.]+),(-?[\d.]+),[^,]*,(NULL|'[^']*')")
_WORD = r"[A-ZÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻА-ЯЁ][\w'’.-]*"
_CONNECTOR = r"(?:de|di|del|della|du|des|la|le|al|el|am|an|der|von|van|op|aan|nad|pod|на|под|-)"
_PHRASE = re.compile(rf"{_WORD}(?:\s+(?:{_CONNECTOR}\s+)?{_WORD}){{0,3}}")


def _normal(title):
    title = re.sub(r"[\s_]+", " ", title).strip()
    return title[:1].upper() + title[1:]


def name_key(title):
    """The bare name of a place, as a text might write it: "Alexandria (Virginia)" and
    "Alexandria, Egypt" are both "alexandria"."""
    title = re.sub(r"\s*\([^)]*\)", "", title)
    return title.split(",")[0].strip().lower()


def _infobox_pattern(lang):
    return INFOBOX if lang == "en" else LANGUAGES[lang].infobox


def _place_field(lang):
    return "place" if lang == "en" else LANGUAGES[lang].place


def _without_infobox(lang, text):
    """The text with the battle's infobox cut out."""
    match = _infobox_pattern(lang).search(text)
    if match is None:
        return text
    depth, i = 1, match.end()
    while i < len(text) and depth:
        pair = text[i:i + 2]
        if pair == "{{":
            depth, i = depth + 1, i + 2
        elif pair == "}}":
            depth, i = depth - 1, i + 2
        else:
            i += 1
    return text[:match.start()] + text[i:]


def _links(text):
    found = []
    for target in _LINK.findall(text):
        title = _normal(target)
        if title and ":" not in title and not land_of(title) and title not in found:
            found.append(title)
    return found


def linked_places(lang, wikitext):
    """[(title, kind)]: the links of the infobox's place field ("infobox"), then those of the text
    ("artikel"). Whether each is a place is decided by its coordinates."""
    text = strip_comments(wikitext)
    fields = find_infobox(text, _infobox_pattern(lang)) or {}
    result = [(title, "infobox") for title in _links(fields.get(_place_field(lang), ""))]
    seen = {title for title, _ in result}
    for title in _links(_without_infobox(lang, text)):
        if title not in seen:
            seen.add(title)
            result.append((title, "artikel"))
    return result


def _plain(text):
    """The running text: no templates, references, tags or links (linked names are counted apart)."""
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{[^{}]*\}\}", " ", text)
    text = re.sub(r"\[\[[^\]]*\]\]", " | ", text)
    text = re.sub(r"\[https?://[^\]]*\]|<[^>]+>|'''?", " ", text)
    return text


def name_candidates(lang, wikitext):
    """The bare names (see name_key) of capitalised word groups in the text outside links, and
    of every shorter run of words in them: "In Bir Hakeim" also gives "bir hakeim"."""
    if lang not in CAPITALISED:
        return set()
    keys = set()
    for match in _PHRASE.finditer(_plain(_without_infobox(lang, strip_comments(wikitext)))):
        words = match.group(0).split()
        for start in range(len(words)):
            for end in range(start + 1, len(words) + 1):
                key = " ".join(words[start:end]).strip(".’'-").lower()
                if len(key) >= 4 and not land_of(key):
                    keys.add(key)
    return keys


def read_geotags(path):
    """Page id → (lat, lng, type) of every page's primary position on earth."""
    found = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as lines:
        for line in lines:
            for _, page_id, lat, lng, kind in _GEO_ROW.findall(line):
                kind = None if kind == "NULL" else kind.strip("'")
                if kind not in NOT_PLACES:
                    found[int(page_id)] = (float(lat), float(lng), kind)
    return found


def _redirect_targets(sql_gz_path, ids):
    found = {}
    with gzip.open(sql_gz_path, "rt", encoding="utf-8", errors="replace") as lines:
        for line in lines:
            for page_id, namespace, title in _SQL_ROW.findall(line):
                if namespace == "0" and int(page_id) in ids:
                    found[int(page_id)] = _normal(_unescape(title))
    return found


def build_places(index, redirects, geotags, link_titles, db_path):
    """Fills db_path with every place (bare name, title, lat, lng, type) and returns the
    positions of the linked titles, redirects followed: title → (lat, lng, type)."""
    places = read_geotags(geotags)
    db = sqlite3.connect(db_path)
    db.execute("DROP TABLE IF EXISTS places")
    db.execute("CREATE TABLE places (key TEXT, title TEXT, lat REAL, lng REAL, type TEXT)")
    link_ids, title_ids, rows = {}, {}, []
    for _, page_id, title in _index_rows(index):
        if title in link_titles:
            link_ids[title] = page_id
        if page_id in places:
            lat, lng, kind = places[page_id]
            title_ids[title] = page_id
            rows.append((name_key(title), title, lat, lng, kind))
            if len(rows) >= 50_000:
                db.executemany("INSERT INTO places VALUES (?, ?, ?, ?, ?)", rows)
                rows.clear()
    db.executemany("INSERT INTO places VALUES (?, ?, ?, ?, ?)", rows)
    db.execute("CREATE INDEX places_key ON places (key)")
    db.commit()
    db.close()
    targets = _redirect_targets(redirects, set(link_ids.values()))
    positions = {}
    for title, page_id in link_ids.items():
        target = targets.get(page_id, title)
        target_id = page_id if target == title else title_ids.get(target)
        if target_id in places and land_of(target) is None:
            positions[title] = places[target_id]
    return positions


def lookup_names(db_path, keys):
    """Bare name → [(title, lat, lng)] of the places a name without a link may mean."""
    db = sqlite3.connect(db_path)
    found = {}
    keys = list(keys)
    for start in range(0, len(keys), 500):
        chunk = keys[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for key, title, lat, lng, kind in db.execute(
                f"SELECT key, title, lat, lng, type FROM places WHERE key IN ({marks})", chunk):
            if kind in NAMED_TYPES:
                found.setdefault(key, []).append((title, lat, lng))
    db.close()
    return found


def distance_km(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1.0, h)))


def choose(candidates, anchors):
    """The place a name without a link stands for: nearest to the anchors (at most
    MAX_DISTANCE_KM away), or, without anchors, the only one. None when unsure."""
    if anchors:
        best = min(candidates, key=lambda c: min(distance_km((c[1], c[2]), a) for a in anchors))
        near = min(distance_km((best[1], best[2]), a) for a in anchors)
        return best if near <= MAX_DISTANCE_KM else None
    return candidates[0] if len(candidates) == 1 else None


def hints_for(links, positions, names, named):
    """The Plaatshints of one Veldslag.

    links: [(lang, title, kind)] of its linked places; positions: {(lang, title): (lat, lng, type)};
    names: [(lang, key)] of its names without a link; named: {(lang, key): [(title, lat, lng)]}."""
    hints, seen = [], set()
    for lang, title, kind in links:
        position = positions.get((lang, title))
        if position and title not in seen:
            seen.add(title)
            hints.append({"name": title, "lat": position[0], "lng": position[1], "kind": kind})
    anchors = [(h["lat"], h["lng"]) for h in hints]
    for lang, key in names:
        candidates = named.get((lang, key))
        if not candidates:
            continue
        chosen = choose(candidates, anchors)
        if chosen and chosen[0] not in seen:
            seen.add(chosen[0])
            hints.append({"name": chosen[0], "lat": chosen[1], "lng": chosen[2], "kind": "artikel"})
    hints.sort(key=lambda hint: hint["kind"] != "infobox")
    return hints[:MAX_HINTS]


def _files(directory, lang):
    names = ("pages-articles-multistream-index.txt.bz2", "redirect.sql.gz", "geo_tags.sql.gz")
    paths = []
    for name in names:
        found = sorted(Path(directory).expanduser().glob(f"{lang}wiki-*-{name}"))
        if not found:
            return None
        paths.append(found[-1])
    return paths


def run(battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE, english_dir=ENGLISH_DIR, other_dir=OTHER_DIR):
    battles = json.loads(Path(battles_path).read_text(encoding="utf-8"))
    engine = create_engine(database_url)
    BattleHints.__table__.create(engine, checkfirst=True)
    with Session(engine) as session:
        english = dict(session.execute(select(BattleArticle.title, BattleArticle.wikitext)).all())
        foreign = {}
        for lang, title, battle, wikitext in session.execute(select(
                ForeignBattleArticle.lang, ForeignBattleArticle.title, ForeignBattleArticle.battle,
                ForeignBattleArticle.wikitext)).all():
            # An article belongs to the Veldslag the merge gave it, or, not merged yet, to the
            # Veldslag of its own language and title; languages this code does not know wait.
            if lang in LANGUAGES:
                foreign.setdefault(battle or title, []).append((lang, wikitext, battle is not None))
    links, names = {}, {}
    for battle in battles:
        sources = []
        if battle.get("lang", "en") == "en" and battle["title"] in english:
            sources.append(("en", english[battle["title"]]))
        sources += [(lang, text) for lang, text, owned in foreign.get(battle["title"], [])
                    if owned or battle.get("lang") == lang]
        links[battle["title"]] = [(lang, title, kind) for lang, text in sources for title, kind in linked_places(lang, text)]
        names[battle["title"]] = [(lang, key) for lang, text in sources for key in sorted(name_candidates(lang, text))]
    positions, named = {}, {}
    scratch = Path(other_dir).expanduser() / "places.sqlite"
    for lang in sorted({lang for found in links.values() for lang, _, _ in found}):
        files = _files(english_dir if lang == "en" else other_dir, lang)
        if files is None:
            print(f"{lang}: no index, redirects or geo_tags, skipped", file=sys.stderr)
            continue
        titles = {title for found in links.values() for link_lang, title, _ in found if link_lang == lang}
        print(f"{lang}: {len(titles)} linked titles…", file=sys.stderr, flush=True)
        for title, position in build_places(*files, titles, scratch).items():
            positions[(lang, title)] = position
        keys = {key for found in names.values() for name_lang, key in found if name_lang == lang}
        for key, candidates in lookup_names(scratch, keys).items():
            named[(lang, key)] = candidates
        scratch.unlink()
    now = datetime.now(timezone.utc)
    with_hints = 0
    rows = []
    for battle in battles:
        hints = hints_for(links[battle["title"]], positions, names[battle["title"]], named)
        if hints:
            with_hints += 1
            rows.append(BattleHints(battle=battle["title"], hints_json=json.dumps(hints, ensure_ascii=False),
                                    computed_at=now))
    # One short transaction, so the server and the crawls never find the database locked for long.
    with Session(engine) as session, session.begin():
        session.execute(delete(BattleHints))
        session.add_all(rows)
    engine.dispose()
    print(f"{with_hints} of {len(battles)} Veldslagen have Plaatshints")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="battles.json, whose Veldslagen get hints")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the articles; receives the hints")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.database)


if __name__ == "__main__":
    main()

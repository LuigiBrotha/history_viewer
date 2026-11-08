"""Plaatshints: where a Veldslag without a position may have been, from the places its articles link.

The `place` field of the infobox gives hints of kind "infobox"; the places linked in the text
(after the infobox) give hints of kind "artikel". A linked article counts as a place when it
has coordinates of its own; countries are left out (their coordinates are a capital or a
middle). The coordinates come from the dumps, so nothing is looked up online. Each language's
dump is read only at the streams that hold the wanted places:

    poetry run python -m tools.place_hints [--battles FILE] [--database URL]

The hints go in battles.json as `hints`: [{"name", "lat", "lng", "kind"}], only for battles
without a position; the page shows them when such a battle is selected.
"""

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import BattleArticle, ForeignBattleArticle
from tools.countries import land_of
from tools.extract_battles import (
    DEFAULT_DATABASE,
    DEFAULT_OUTPUT,
    INFOBOX,
    _write_atomically,
    checked,
    extract_coordinates,
    find_infobox,
    strip_comments,
)
from tools.fill_battle_articles import _SQL_ROW, _index_rows, _unescape, read_pages
from tools.wiki_languages import LANGUAGES, _degree_fields, _slash_pair, other_coordinates

ENGLISH_DIR = Path("~/.cache/uboats/wikipedia")
OTHER_DIR = Path("~/.cache/uboats/wikipedia/other")
MAX_TEXT_LINKS = 60
MAX_HINTS = 25
_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def _normal(title):
    title = re.sub(r"[\s_]+", " ", title).strip()
    return title[:1].upper() + title[1:]


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
    """[(title, kind)]: the links of the infobox's place field ("infobox"), then the first links
    of the text ("artikel"). Whether each is a place is decided by its coordinates later."""
    text = strip_comments(wikitext)
    fields = find_infobox(text, _infobox_pattern(lang)) or {}
    result = [(title, "infobox") for title in _links(fields.get(_place_field(lang), ""))]
    seen = {title for title, _ in result}
    for title in _links(_without_infobox(lang, text))[:MAX_TEXT_LINKS]:
        if title not in seen:
            seen.add(title)
            result.append((title, "artikel"))
    return result


_DECIMAL_FIELDS = (
    ("latitude", "longitude"), ("lat", "long"), ("lat", "lon"), ("breitengrad", "längengrad"),
    ("latitudine decimale", "longitudine decimale"), ("широта", "долгота"),
)


def _field(text, name):
    match = re.search(rf"\|\s*{re.escape(name)}\s*=\s*([^|\n}}]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


# The infobox of a country (or a former one) in each language: its article is no place.
_COUNTRY = re.compile(
    r"\{\{\s*(?:infobox[\s_]+(?:former[\s_]+)?country|infobox[\s_]+land|infobox[\s_]+staat|infobox[\s_]+pays|"
    r"stato|государство|państwo[\s_]+infobox|基礎情報[\s_]+国)\s*(?=[|\n}])",
    re.IGNORECASE,
)


def place_coordinates(lang, text):
    """The position of a place article, in any of the ways its language writes one; None if none."""
    text = strip_comments(text)
    if _COUNTRY.search(text):
        return None
    lat, lng = extract_coordinates(text) if lang == "en" else other_coordinates(lang, text)
    if lat is not None:
        return lat, lng
    for lat_name, lng_name in _DECIMAL_FIELDS:
        lat_text, lng_text = _field(text, lat_name), _field(text, lng_name)
        if lat_text and lng_text:
            position = _slash_pair(lat_text.replace(",", "."), lng_text.replace(",", "."))
            if position:
                return position
    # Polish settlements: stopniN, minutN, sekundN, stopniE, …
    if _field(text, "stopniN") and _field(text, "stopniE"):
        def value(axis):
            return "/".join(_field(text, f"{unit}{axis}") or "0" for unit in ("stopni", "minut", "sekund"))
        position = _slash_pair(value("N"), value("E"))
        if position:
            return position
    return _degree_fields(text)


def _redirect_targets(sql_gz_path, ids):
    found = {}
    with gzip.open(sql_gz_path, "rt", encoding="utf-8", errors="replace") as lines:
        for line in lines:
            for page_id, namespace, title in _SQL_ROW.findall(line):
                if namespace == "0" and int(page_id) in ids:
                    found[int(page_id)] = _normal(_unescape(title))
    return found


def place_positions(lang, dump, index, redirects, titles):
    """Title → (lat, lng) of the wanted titles that are places, following redirects."""
    wanted = set(titles)
    located = {title: (offset, page_id) for offset, page_id, title in _index_rows(index) if title in wanted}
    targets = _redirect_targets(redirects, {page_id for _, page_id in located.values()})
    final = {title: targets.get(page_id, title) for title, (_, page_id) in located.items()}
    missing = set(final.values()) - set(located)
    if missing:
        located.update({title: (offset, page_id) for offset, page_id, title in _index_rows(index)
                        if title in missing})
    pages = {final_title for final_title in final.values() if final_title in located}
    positions = {}
    for title, text in read_pages(dump, [located[t][0] for t in pages]):
        if title in pages and (position := place_coordinates(lang, text)) is not None:
            positions[title] = position
    return {title: positions[target] for title, target in final.items() if target in positions}


def hints_for(links, positions):
    """[{"name", "lat", "lng", "kind"}] from [(lang, title, kind)] and {(lang, title): position}."""
    hints, seen = [], set()
    for lang, title, kind in links:
        position = positions.get((lang, title))
        if position is None or title in seen:
            continue
        seen.add(title)
        hints.append({"name": title, "lat": position[0], "lng": position[1], "kind": kind})
    # The infobox's places first, then the text's, at most MAX_HINTS in all.
    hints.sort(key=lambda hint: hint["kind"] != "infobox")
    return hints[:MAX_HINTS]


def _files(directory, lang):
    names = ("pages-articles-multistream.xml.bz2", "pages-articles-multistream-index.txt.bz2", "redirect.sql.gz")
    paths = []
    for name in names:
        found = sorted(Path(directory).expanduser().glob(f"{lang}wiki-*-{name}"))
        if not found:
            return None
        paths.append(found[-1])
    return paths


def run(battles_path=DEFAULT_OUTPUT, database_url=DEFAULT_DATABASE, english_dir=ENGLISH_DIR, other_dir=OTHER_DIR):
    battles_path = Path(battles_path)
    battles = json.loads(battles_path.read_text(encoding="utf-8"))
    engine = create_engine(database_url)
    with Session(engine) as session:
        english = dict(session.execute(select(BattleArticle.title, BattleArticle.wikitext)).all())
        foreign = {}
        for lang, title, battle, wikitext in session.execute(select(
                ForeignBattleArticle.lang, ForeignBattleArticle.title, ForeignBattleArticle.battle,
                ForeignBattleArticle.wikitext)).all():
            foreign.setdefault(battle or title, []).append((lang, wikitext))
    engine.dispose()
    unplaced = [b for b in battles if b.get("lat") is None or b.get("lng") is None]
    links = {}
    for battle in unplaced:
        sources = []
        if battle.get("lang", "en") == "en" and battle["title"] in english:
            sources.append(("en", english[battle["title"]]))
        sources += foreign.get(battle["title"], [])
        links[battle["title"]] = [(lang, title, kind) for lang, text in sources
                                  for title, kind in linked_places(lang, text)]
    positions = {}
    for lang in sorted({lang for found in links.values() for lang, _, _ in found}):
        files = _files(english_dir if lang == "en" else other_dir, lang)
        if files is None:
            print(f"{lang}: no dump, index or redirects, skipped", file=sys.stderr)
            continue
        titles = {title for found in links.values() for link_lang, title, _ in found if link_lang == lang}
        print(f"{lang}: looking up {len(titles)} linked titles…", file=sys.stderr, flush=True)
        for title, position in place_positions(lang, *files, titles).items():
            positions[(lang, title)] = position
    with_hints = 0
    unplaced_titles = {battle["title"] for battle in unplaced}
    for battle in battles:
        hints = hints_for(links.get(battle["title"], []), positions) if battle["title"] in unplaced_titles else []
        if hints:
            battle["hints"] = hints
            with_hints += 1
        else:
            battle.pop("hints", None)
    _write_atomically(battles_path, json.dumps(battles, ensure_ascii=False, separators=(",", ":")))
    print(f"{with_hints} of {len(unplaced)} Veldslagen without a position have plaatshints")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="the battles.json to add plaatshints to")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the stored articles (an SQLite URL)")
    arguments = parser.parse_args(argv)
    run(arguments.battles, arguments.database)


if __name__ == "__main__":
    main()

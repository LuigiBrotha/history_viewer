"""The English article title of pages of another Wikipedia, through its redirects and language links.

A Russian infobox links [[Жуков, Георгий Константинович]]; the English Wikipedia calls him
Georgy Zhukov. Each language's index, redirect.sql and langlinks.sql are streamed a few times
for the wanted titles only, so memory stays small. The result is kept as
`<lang>wiki-names.json` next to the dumps, and tools.enrich_battles reads it:

    poetry run python -m tools.english_names [--dir DIR] [--database URL]
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import ForeignBattleArticle
from tools.extract_battles import DEFAULT_DATABASE, _write_atomically
from tools.fill_battle_articles import _SQL_ROW, _index_rows, _unescape
from tools.merge_languages import read_langlinks
from tools.wiki_languages import ORDER

DEFAULT_DIR = Path("~/.cache/uboats/wikipedia/other")


def _normal(title):
    title = title.replace("_", " ").strip()
    return title[:1].upper() + title[1:]


def ids_for_titles(index_path, titles):
    """Title → page id, for the wanted titles only."""
    return {title: page_id for _, page_id, title in _index_rows(index_path) if title in titles}


def redirect_targets(sql_gz_path, ids):
    """Page id → the article title it redirects to, for the wanted page ids only."""
    found = {}
    with gzip.open(sql_gz_path, "rt", encoding="utf-8", errors="replace") as lines:
        for line in lines:
            for page_id, namespace, title in _SQL_ROW.findall(line):
                if namespace == "0" and int(page_id) in ids:
                    found[int(page_id)] = _normal(_unescape(title))
    return found


def english_titles(index_path, redirect_path, langlinks_path, titles):
    """Title (as linked) → the English article title, for those that have one."""
    wanted = {_normal(t) for t in titles}
    ids = ids_for_titles(index_path, wanted)
    redirected = redirect_targets(redirect_path, set(ids.values()))
    # A link may point at a redirect; follow it to the article.
    final = {title: redirected.get(page_id, title) for title, page_id in ids.items()}
    missing = set(final.values()) - set(ids)
    if missing:
        ids.update(ids_for_titles(index_path, missing))
    article_ids = {ids[target] for target in final.values() if target in ids}
    links = read_langlinks(langlinks_path, article_ids, {"en"})
    result = {}
    for title in titles:
        target = final.get(_normal(title))
        english = links.get(ids.get(target), {}).get("en") if target else None
        if english:
            result[title] = _normal(english)
    return result


def _latest(directory, pattern):
    candidates = sorted(directory.glob(pattern))
    return candidates[-1] if candidates else None


def run(directory=DEFAULT_DIR, database_url=DEFAULT_DATABASE, languages=ORDER):
    from tools.enrich_battles import people_and_units

    directory = Path(directory).expanduser()
    engine = create_engine(database_url)
    with Session(engine) as session:
        articles = session.execute(select(ForeignBattleArticle.lang, ForeignBattleArticle.title,
                                          ForeignBattleArticle.wikitext)).all()
    engine.dispose()
    for lang in languages:
        paths = [_latest(directory, f"{lang}wiki-*-{name}") for name in
                 ("pages-articles-multistream-index.txt.bz2", "redirect.sql.gz", "langlinks.sql.gz")]
        if None in paths:
            print(f"{lang}: index, redirects or langlinks missing, skipped")
            continue
        names = set()
        for article_lang, title, wikitext in articles:
            if article_lang == lang:
                names.add(title)
                people, units = people_and_units(lang, wikitext)
                names.update(people)
                names.update(units)
        print(f"{lang}: {len(names)} titles and names…", file=sys.stderr, flush=True)
        found = english_titles(*paths, names)
        _write_atomically(directory / f"{lang}wiki-names.json", json.dumps(found, ensure_ascii=False))
        print(f"{lang}: {len(found)} of {len(names)} have an English article")


def read_names(directory=DEFAULT_DIR):
    """Language → {title: English title}, from the files run() wrote."""
    directory = Path(directory).expanduser()
    names = {}
    for path in directory.glob("*wiki-names.json"):
        names[path.name.split("wiki-")[0]] = json.loads(path.read_text(encoding="utf-8"))
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dir", default=DEFAULT_DIR, help="directory with the dumps of the other languages")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the stored articles (an SQLite URL)")
    arguments = parser.parse_args(argv)
    run(arguments.dir, arguments.database)


if __name__ == "__main__":
    main()

"""List the Veldslagen of each Eenheid and Bevelhebber from their own English articles.

The articles of military units and people have a `battles` field in their infobox. The dump
is streamed once (memory stays small; redirects wait in a scratch SQLite file next to the
result), and a stopped run continues where it was:

    poetry run python -m tools.extract_unit_battles [dump.xml.bz2 | directory] [--battles FILE] [--output FILE]

The result, {"units": {title: [Veldslagen]}, "people": {…}, "aliases": {redirect: title}},
is read by tools.enrich_battles.
"""

import argparse
import html
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from tools.enrich_battles import linked_names
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.storage.models import BattleRedirect
from tools.extract_battles import (
    DEFAULT_DATABASE,
    DEFAULT_DUMP,
    DEFAULT_OUTPUT,
    _write_atomically,
    find_infobox,
    iter_raw_pages,
    resolve_dump,
)

DEFAULT_RESULT = Path("~/.cache/uboats/wikipedia/unit_battles.json")
SAVE_EVERY_SECONDS = 60
PROGRESS_EVERY = 500_000
CANDIDATE = re.compile(rb"infobox[ _]+military[ _]+(?:unit|person)", re.IGNORECASE)
INFOBOX = re.compile(r"\{\{\s*infobox[\s_]+military[\s_]+(unit|person)\s*(?=[|\n}]|$)", re.IGNORECASE)
_TITLE = re.compile(rb"<title>(.*?)</title>", re.DOTALL)
_NS = re.compile(rb"<ns>(\d+)</ns>")
_REDIRECT = re.compile(rb'<redirect title="([^"]*)"')
_TEXT = re.compile(rb"<text[^>]*>(.*?)(?:</text>|$)", re.DOTALL)


def _decode(raw):
    return html.unescape(raw.decode("utf-8", errors="replace"))


def _battle_aliases(database_url):
    """The stored redirects to Veldslagen (alias → title); none when there is no such table."""
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            return dict(session.execute(select(BattleRedirect.alias, BattleRedirect.title)).all())
    except Exception:
        return {}
    finally:
        engine.dispose()


def run(dump=DEFAULT_DUMP, battles_path=DEFAULT_OUTPUT, output=DEFAULT_RESULT, save_every_seconds=SAVE_EVERY_SECONDS,
        database_url=DEFAULT_DATABASE):
    output = Path(output).expanduser()
    state = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    if state and state.get("complete"):
        print(f"{output} is complete; delete it to scan again")
        return
    state = state or {"complete": False, "pages": 0, "units": {}, "people": {}, "aliases": {}}
    dump = resolve_dump(dump)
    veldslagen = {battle["title"] for battle in json.loads(Path(battles_path).read_text(encoding="utf-8"))}
    # A battles field may link a Veldslag through one of its redirects.
    resolve = {title: title for title in veldslagen}
    resolve.update({alias: title for alias, title in _battle_aliases(database_url).items() if title in veldslagen})
    scratch_path = output.with_name(output.stem + ".redirects.sqlite")
    scratch = sqlite3.connect(scratch_path)
    scratch.execute("CREATE TABLE IF NOT EXISTS redirects (alias TEXT PRIMARY KEY, target TEXT)")
    redirects = []
    pages = state["pages"]

    def save(complete=False):
        scratch.executemany("INSERT OR REPLACE INTO redirects VALUES (?, ?)", redirects)
        scratch.commit()
        redirects.clear()
        state["pages"] = pages
        state["complete"] = complete
        _write_atomically(output, json.dumps(state, ensure_ascii=False))

    last_save = time.monotonic()
    for pages, raw in enumerate(iter_raw_pages(dump), 1):
        if pages <= state["pages"]:
            continue
        redirect = _REDIRECT.search(raw)
        candidate = redirect is None and CANDIDATE.search(raw) is not None
        if redirect is not None or candidate:
            ns = _NS.search(raw)
            title = _TITLE.search(raw)
            if ns is not None and ns.group(1) == b"0" and title is not None:
                if redirect is not None:
                    redirects.append((_decode(title.group(1)), _decode(redirect.group(1))))
                else:
                    text = _TEXT.search(raw)
                    wikitext = _decode(text.group(1)) if text else ""
                    match = INFOBOX.search(wikitext)
                    fields = find_infobox(wikitext, INFOBOX) or {}
                    battles = []
                    for name in linked_names(fields.get("battles", "")):
                        if name in resolve and resolve[name] not in battles:
                            battles.append(resolve[name])
                    if match and battles:
                        kind = "units" if match.group(1).lower() == "unit" else "people"
                        state[kind][_decode(title.group(1))] = battles
        if time.monotonic() - last_save >= save_every_seconds:
            save()
            last_save = time.monotonic()
        if pages % PROGRESS_EVERY == 0:
            print(f"{pages} pages read, {len(state['units'])} units, {len(state['people'])} people",
                  file=sys.stderr, flush=True)
    save()
    titles = set(state["units"]) | set(state["people"])
    state["aliases"] = {alias: target for alias, target in scratch.execute("SELECT alias, target FROM redirects")
                        if target in titles}
    state["complete"] = True
    _write_atomically(output, json.dumps(state, ensure_ascii=False))
    scratch.close()
    scratch_path.unlink()
    print(f"{len(state['units'])} units and {len(state['people'])} people with Veldslagen, "
          f"{len(state['aliases'])} other names")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dump", nargs="?", default=DEFAULT_DUMP, help="the .xml.bz2 dump, or the directory holding it")
    parser.add_argument("--battles", default=DEFAULT_OUTPUT, help="battles.json, whose titles count as Veldslagen")
    parser.add_argument("--output", default=DEFAULT_RESULT, help="where to write the result")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="database with the redirects to the Veldslagen")
    arguments = parser.parse_args(argv)
    run(arguments.dump, arguments.battles, arguments.output, database_url=arguments.database)


if __name__ == "__main__":
    main()

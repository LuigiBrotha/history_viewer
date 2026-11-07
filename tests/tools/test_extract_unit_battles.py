import bz2
import gzip
import json
from xml.sax.saxutils import escape

import pytest

from tools.extract_unit_battles import run


@pytest.fixture(autouse=True)
def database_in_tmp_path(tmp_path, monkeypatch):
    """run() defaults to ./uboats.db; keep the tests away from any real one."""
    monkeypatch.chdir(tmp_path)

UNIT = ("{{Infobox military unit\n| unit_name = 7th Panzer Division\n| battles = [[Battle of France]]<br>"
        "[[Operation Barbarossa|Barbarossa]]<br>[[Battle of Waterloo]]\n}}")
PERSON = ("{{Infobox military person\n| name = Erwin Rommel\n| battles = {{plainlist|\n* [[Battle of France]]\n"
          "* [[Western Desert campaign]]\n* [[Operation Barbarossa]]\n}}\n}}")


def page(page_id, title, text, redirect=None):
    tag = f'<redirect title="{escape(redirect)}" />' if redirect else ""
    return (f"<page><title>{escape(title)}</title><ns>0</ns><id>{page_id}</id>{tag}"
            f"<revision><text>{escape(text)}</text></revision></page>")


def files(tmp_path):
    body = "".join([
        page(1, "7th Panzer Division (Wehrmacht)", UNIT),
        page(2, "Erwin Rommel", PERSON),
        page(3, "Plain", "Just text."),
        page(4, "Rommel", "#REDIRECT [[Erwin Rommel]]", redirect="Erwin Rommel"),
    ])
    dump = tmp_path / "enwiki-20261001-pages-articles.xml.bz2"
    dump.write_bytes(bz2.compress(f'<mediawiki xmlns="x">{body}</mediawiki>'.encode("utf-8")))
    battles = tmp_path / "battles.json"
    battles.write_text(json.dumps([{"title": "Battle of France"}, {"title": "Operation Barbarossa"},
                                   {"title": "Western Desert campaign"}]), encoding="utf-8")
    return dump, battles, tmp_path / "unit_battles.json"


def test_run_lists_the_veldslagen_of_units_and_people_with_their_other_names(tmp_path):
    dump, battles, out = files(tmp_path)
    run(dump, battles, out)
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["units"] == {"7th Panzer Division (Wehrmacht)": ["Battle of France", "Operation Barbarossa"]}
    assert result["people"] == {"Erwin Rommel": ["Battle of France", "Western Desert campaign", "Operation Barbarossa"]}
    assert result["aliases"] == {"Rommel": "Erwin Rommel"}
    assert result["complete"] is True


def test_a_complete_result_is_not_scanned_again(tmp_path):
    dump, battles, out = files(tmp_path)
    run(dump, battles, out)
    first = out.read_text(encoding="utf-8")
    dump.write_bytes(b"not a dump")
    run(dump, battles, out)
    assert out.read_text(encoding="utf-8") == first


def test_battles_linked_through_a_redirect_count(tmp_path):
    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.services.storage.models import Base, BattleArticle, BattleRedirect

    dump, battles, out = files(tmp_path)
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        session.add(BattleArticle(title="Western Desert campaign", wikitext="x", dump_name="d",
                                  extracted_at=datetime.now(timezone.utc)))
        session.flush()
        session.add(BattleRedirect(alias="Battle of Waterloo", title="Western Desert campaign"))
    engine.dispose()
    run(dump, battles, out, database_url=url)
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["units"]["7th Panzer Division (Wehrmacht)"] == ["Battle of France", "Operation Barbarossa",
                                                                  "Western Desert campaign"]

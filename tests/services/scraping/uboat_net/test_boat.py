from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.boat import parse_boat

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "u99.htm"


def test_parse_boat_extracts_all_fields_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    boat = parse_boat(html, "u99")

    assert boat.slug == "u99"
    assert boat.number == "U-99"
    assert boat.type == "VIIB"
    assert boat.builder == "F. Krupp Germaniawerft AG, Kiel"
    assert boat.laid_down == date(1939, 3, 31)
    assert boat.launched == date(1940, 3, 12)
    assert boat.commissioned == date(1940, 4, 18)
    assert boat.fate is not None
    assert "Scuttled" in boat.fate


def test_parse_boat_falls_back_to_slug_when_no_h1_present():
    boat = parse_boat("<html><body>no name here</body></html>", "u1")

    assert boat.number == "u1"
    assert boat.type is None
    assert boat.fate is None


def test_parse_boat_missing_profile_table_returns_none_fields():
    boat = parse_boat("<h1>uboat.net</h1><h1>U-1</h1>", "u1")

    assert boat.number == "U-1"
    assert boat.type is None
    assert boat.laid_down is None

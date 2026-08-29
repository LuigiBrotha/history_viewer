from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.patrol_list import parse_patrol_list

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "patrols_u99.html"
_PAGE_URL = "https://uboat.net/boats/patrols/u99.html"


def test_parse_patrol_list_extracts_all_eight_patrols_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    summaries = parse_patrol_list(html, _PAGE_URL)

    assert len(summaries) == 8
    assert [s.patrol_number for s in summaries] == list(range(1, 9))


def test_parse_patrol_list_first_patrol_fields():
    html = _FIXTURE.read_text(encoding="utf-8")

    first = parse_patrol_list(html, _PAGE_URL)[0]

    assert first.external_id == "patrol_4754"
    assert first.commander == "Kptlt. Otto Kretschmer"
    assert first.departure_port == "Kiel"
    assert first.departure_date == date(1940, 6, 18)
    assert first.arrival_port == "Wilhelmshaven"
    assert first.arrival_date == date(1940, 6, 25)
    assert first.days_at_sea == 8
    assert first.tonnage is None
    assert first.detail_url == "https://uboat.net/boats/patrols/patrol_4754.html"


def test_parse_patrol_list_parses_tonnage_when_present():
    html = _FIXTURE.read_text(encoding="utf-8")

    second = parse_patrol_list(html, _PAGE_URL)[1]

    assert second.tonnage == 22719


def test_parse_patrol_list_stores_fate_text_as_arrival_port_when_boat_was_lost():
    html = _FIXTURE.read_text(encoding="utf-8")

    last = parse_patrol_list(html, _PAGE_URL)[-1]

    assert last.arrival_port == "Sunk"


def test_parse_patrol_list_missing_table_returns_empty_list():
    assert parse_patrol_list("<html><body>nothing here</body></html>", _PAGE_URL) == []


def _row_html(patrol_number_text, tonnage_text, external_id="patrol_9999"):
    return f"""
    <table class="table_subtle">
    <tr bgcolor="#f0f0f0">
        <td class="width20 right">{patrol_number_text}</td>
        <td>Kptlt. Someone</td>
        <td class="right non-breaking">18 Jun 1940</td>
        <td>Kiel</td>
        <td class="right non-breaking">25 Jun 1940</td>
        <td>Wilhelmshaven</td>
        <td class="right">8 days</td>
        <td class="right">{tonnage_text}</td>
        <td>&nbsp;P</td>
        <td>&nbsp;<a href="{external_id}.html">View</a></td>
    </tr>
    </table>
    """


def test_parse_patrol_list_non_numeric_patrol_number_cell_does_not_raise():
    html = _row_html("⌊", "")

    summaries = parse_patrol_list(html, _PAGE_URL)

    assert len(summaries) == 1
    assert summaries[0].patrol_number == 1
    assert summaries[0].external_id == "patrol_9999"


def test_parse_patrol_list_non_numeric_tonnage_cell_does_not_raise():
    html = _row_html("1", "n/a")

    summaries = parse_patrol_list(html, _PAGE_URL)

    assert len(summaries) == 1
    assert summaries[0].tonnage is None

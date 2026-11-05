from pathlib import Path

from app.services.scraping.uboat_net.ship import (
    fetch_ship_page,
    parse_ship_details,
    parse_ship_position,
)

_SHIP_408 = (Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "ship_408.html").read_text(
    encoding="utf-8"
)


def test_position_converts_degrees_and_minutes_with_west_negative():
    lat, lng = parse_ship_position(_SHIP_408)

    assert (round(lat, 4), round(lng, 4)) == (50.5167, -11.0833)


def test_position_south_and_east():
    html = "<table><tr><td><strong>Position</strong></td><td>33&deg; 30'S, 18&deg; 00'E - Grid CP 1</td></tr></table>"

    assert parse_ship_position(html) == (-33.5, 18.0)


def test_page_without_a_position_returns_none():
    html = "\n".join(line for line in _SHIP_408.splitlines() if "<strong>Position</strong>" not in line)

    assert "Grid BF" not in html
    assert parse_ship_position(html) is None


def test_details_of_a_ship_page():
    details = parse_ship_details(_SHIP_408)

    assert (
        details.ship_type, details.completed, details.owner, details.homeport, details.nationality,
        details.fate, details.complement, details.convoy, details.route, details.cargo, details.history,
    ) == (
        "Steam merchant",
        "1923 - Frazer Brace Ltd, Three Rivers PQ",
        "Canada Steamship Lines Ltd, Montreal",
        "Montreal",
        "Canadian",
        "Sunk by U-99 (Otto Kretschmer)",
        "23 (0 dead and 23 survivors).",
        "HX-52 (straggler)",
        "Halifax (21 Jun) - Preston",
        "512 standards of timber",
        "Built as John C. Howard, later renamed Magog",
    )
    assert details.notes.startswith("At 12.51 hours on 5 July 1940 the Magog (Master T. Swales Doughty), a straggler")
    assert "convoy HX-52, was damaged" in details.notes
    assert details.notes.endswith("landed at Queenstown, Cork.")


def test_missing_rows_are_none():
    html = "<table><tr><td><strong>Owner</strong></td><td>Acme</td></tr></table>"

    details = parse_ship_details(html)

    assert details.owner == "Acme"
    assert details.ship_type is None and details.nationality is None and details.notes is None


def test_fetch_ship_page_returns_position_and_details():
    class Client:
        def get_text(self, url):
            self.url = url
            return _SHIP_408

    client = Client()
    position, details = fetch_ship_page(client, "https://uboat.net/allies/merchants/ship/408.html")

    assert round(position[0], 4) == 50.5167
    assert details.owner == "Canada Steamship Lines Ltd, Montreal"
    assert client.url == "https://uboat.net/allies/merchants/ship/408.html"

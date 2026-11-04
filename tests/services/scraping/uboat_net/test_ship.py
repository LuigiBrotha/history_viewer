from pathlib import Path

from app.services.scraping.uboat_net.ship import fetch_ship_position, parse_ship_position

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


def test_fetch_ship_position_requests_the_detail_url():
    class Client:
        def get_text(self, url):
            self.url = url
            return _SHIP_408

    client = Client()

    assert fetch_ship_position(client, "https://uboat.net/allies/merchants/ship/408.html") is not None
    assert client.url == "https://uboat.net/allies/merchants/ship/408.html"

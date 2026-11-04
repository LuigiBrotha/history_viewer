from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.successes import fetch_successes, parse_successes
from app.services.scraping.uboat_net.types import ShipHitRef

_FIXTURE = (Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "successes_u99.html").read_text(
    encoding="utf-8"
)


def test_u99_reproduces_the_sites_own_totals():
    hits = parse_successes(_FIXTURE, "u99")

    sunk = [h for h in hits if h.outcome in ("sunk", "captured")]
    damaged = [h for h in hits if h.outcome == "damaged"]
    assert (len(sunk), sum(h.tons for h in sunk)) == (39, 246794)
    assert (len(damaged), sum(h.tons for h in damaged)) == (5, 37965)


def test_first_hit_is_magog():
    assert parse_successes(_FIXTURE, "u99")[0] == ShipHitRef(
        "408", "u99", "Magog", date(1940, 7, 5), 2053, "ca", "HX-52", "sunk",
        "https://uboat.net/allies/merchants/ship/408.html",
    )


def test_captured_and_damaged_markers_are_not_part_of_the_name():
    hits = {h.ship_external_id: h for h in parse_successes(_FIXTURE, "u99")}

    assert (hits["420"].name, hits["420"].outcome) == ("Merisaar", "captured")
    assert (hits["446"].name, hits["446"].outcome) == ("Strinda", "damaged")


def test_boat_without_successes_returns_nothing():
    html = "<html><body><h1>Ships hit by U-1</h1><p>None.</p></body></html>"

    assert parse_successes(html, "u1") == []


def test_fetch_successes_requests_the_boats_page():
    class Client:
        def get_text(self, url):
            self.url = url
            return _FIXTURE

    client = Client()

    assert len(fetch_successes(client, "u99")) == 44
    assert client.url == "https://uboat.net/boats/successes/u99.html"

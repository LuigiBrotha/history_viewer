import re

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.http_client import PoliteHttpClient

_POSITION_RE = re.compile(r"(\d+)\D+(\d+)'\s*([NS])\s*,\s*(\d+)\D+(\d+)'\s*([EW])")


def parse_ship_position(html: str) -> tuple[float, float] | None:
    """Return (lat, lng) from the `Position` row, or None when the page has no usable one."""
    for row in HTMLParser(html).css("tr"):
        cells = row.css("td")
        if len(cells) < 2 or cells[0].text(strip=True) != "Position":
            continue
        match = _POSITION_RE.search(cells[1].text())
        if match is None:
            return None
        lat_deg, lat_min, ns, lng_deg, lng_min, ew = match.groups()
        lat = int(lat_deg) + int(lat_min) / 60
        lng = int(lng_deg) + int(lng_min) / 60
        return (-lat if ns == "S" else lat, -lng if ew == "W" else lng)
    return None


def fetch_ship_position(client: PoliteHttpClient, detail_url: str) -> tuple[float, float] | None:
    return parse_ship_position(client.get_text(detail_url))

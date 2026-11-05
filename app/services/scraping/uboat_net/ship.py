import re

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.http_client import PoliteHttpClient
from app.services.scraping.uboat_net.types import ShipDetails

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


# Label of the row on the ship page -> ShipDetails field.
_DETAIL_ROWS = {
    "Type": "ship_type",
    "Completed": "completed",
    "Owner": "owner",
    "Homeport": "homeport",
    "Fate": "fate",
    "Complement": "complement",
    "Convoy": "convoy",
    "Route": "route",
    "Cargo": "cargo",
    "History": "history",
    "Notes on event": "notes",
}


def _text(node) -> str | None:
    # No separator: tags sit inside sentences, so "(<a>Name</a>)" must stay "(Name)".
    return " ".join(node.text(deep=True, separator="", strip=False).split()) or None


def parse_ship_details(html: str) -> ShipDetails:
    """Read the facts in the table rows of a ship page; rows the page lacks are None."""
    found: dict[str, str | None] = {}
    for row in HTMLParser(html).css("tr"):
        cells = row.css("td")
        if len(cells) < 2:
            continue
        label = (_text(cells[0]) or "").removesuffix(":").strip()
        if label in _DETAIL_ROWS:
            found.setdefault(_DETAIL_ROWS[label], _text(cells[1]))
        for cell in cells[1:]:
            text = _text(cell) or ""
            if text.startswith("Nationality:"):
                found.setdefault("nationality", text.removeprefix("Nationality:").strip() or None)
    return ShipDetails(**found)


def fetch_ship_page(
    client: PoliteHttpClient, detail_url: str
) -> tuple[tuple[float, float] | None, ShipDetails]:
    """One request gives both the position and the details."""
    html = client.get_text(detail_url)
    return parse_ship_position(html), parse_ship_details(html)

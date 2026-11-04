import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_date
from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.types import ShipHitRef

_SHIP_HREF_RE = re.compile(r"/allies/merchants/ship/([^/]+)\.html$")


def _outcome(cell_text: str, link_text: str) -> str:
    """The marker follows the ship's link in the same cell: `Strinda (d.)`, `Merisaar (c.)`."""
    marker = cell_text.replace(link_text, "", 1)
    if "(d.)" in marker:
        return "damaged"
    if "(c.)" in marker:
        return "captured"
    return "sunk"


def parse_successes(html: str, slug: str) -> list[ShipHitRef]:
    parser = HTMLParser(html)
    table = parser.css_first("table.table_subtle")
    if table is None:
        return []

    page_url = f"{BASE_URL}/boats/successes/{slug}.html"
    hits = []
    for row in table.css("tbody tr"):
        cells = row.css("td")
        # Date, commander, picture, ship, tons, flag, nationality, convoy, [map]
        if len(cells) < 8:
            continue
        link = cells[3].css_first("a")
        href = (link.attributes.get("href") or "") if link is not None else ""
        match = _SHIP_HREF_RE.search(href)
        hit_date = parse_date(cells[0].text(strip=True))
        tons_text = cells[4].text(strip=True).replace(",", "")
        if match is None or hit_date is None or not tons_text.isdigit():
            continue

        name = link.text(strip=True)
        hits.append(ShipHitRef(
            ship_external_id=match.group(1),
            boat_slug=slug,
            name=name,
            date=hit_date,
            tons=int(tons_text),
            nationality=cells[6].text(strip=True) or None,
            convoy=cells[7].text(strip=True) or None,
            outcome=_outcome(cells[3].text(strip=True), name),
            detail_url=urljoin(page_url, href),
        ))
    return hits


def fetch_successes(client: PoliteHttpClient, slug: str) -> list[ShipHitRef]:
    return parse_successes(client.get_text(f"{BASE_URL}/boats/successes/{slug}.html"), slug)

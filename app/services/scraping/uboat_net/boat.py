from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_date
from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import BoatData


def _profile_rows(parser: HTMLParser) -> dict[str, list]:
    table = parser.css_first("table.table_subtle")
    rows: dict[str, list] = {}
    if table is None:
        return rows
    for row in table.css("tr"):
        cells = row.css("td")
        if not cells:
            continue
        label = cells[0].text(strip=True)
        rows.setdefault(label, cells)
    return rows


def parse_boat(html: str, slug: str) -> BoatData:
    parser = HTMLParser(html)

    h1_nodes = parser.css("h1")
    number = h1_nodes[-1].text(strip=True) if h1_nodes else slug

    rows = _profile_rows(parser)

    boat_type = None
    if (cells := rows.get("Type")) and len(cells) > 1:
        link = cells[1].css_first("a")
        boat_type = link.text(strip=True) if link else clean_text(cells[1]) or None

    builder = None
    laid_down = None
    if (cells := rows.get("Laid down")):
        if len(cells) > 1:
            laid_down = parse_date(cells[1].text(strip=True))
        if len(cells) > 2:
            link = cells[2].css_first("a")
            builder = link.text(strip=True) if link else clean_text(cells[2]) or None

    launched = None
    if (cells := rows.get("Launched")) and len(cells) > 1:
        launched = parse_date(cells[1].text(strip=True))

    commissioned = None
    if (cells := rows.get("Commissioned")) and len(cells) > 1:
        commissioned = parse_date(cells[1].text(strip=True))

    fate = None
    if (cells := rows.get("Fate")) and len(cells) > 1:
        fate = clean_text(cells[1]) or None

    return BoatData(
        slug=slug,
        number=number,
        type=boat_type,
        builder=builder,
        laid_down=laid_down,
        launched=launched,
        commissioned=commissioned,
        fate=fate,
    )


def fetch_boat(client: PoliteHttpClient, slug: str) -> BoatData:
    html = client.get_text(f"{BASE_URL}/boats/{slug}.htm")
    return parse_boat(html, slug)

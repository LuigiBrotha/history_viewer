import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_date
from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import PatrolSummary

_DAYS_RE = re.compile(r"(\d+)")


def parse_patrol_list(html: str, page_url: str) -> list[PatrolSummary]:
    parser = HTMLParser(html)
    table = parser.css_first("table.table_subtle")
    if table is None:
        return []

    summaries = []
    for row in table.css('tr[bgcolor="#f0f0f0"]'):
        cells = row.css("td")
        if len(cells) < 10:
            continue

        link = cells[9].css_first("a")
        if link is None:
            continue
        href = link.attributes.get("href") or ""
        detail_url = urljoin(page_url, href)
        external_id = href.rsplit("/", 1)[-1].removesuffix(".html")

        days_text = cells[6].text(strip=True)
        days_match = _DAYS_RE.match(days_text)

        tonnage_text = cells[7].text(strip=True)

        summaries.append(PatrolSummary(
            external_id=external_id,
            patrol_number=int(cells[0].text(strip=True) or 0),
            commander=clean_text(cells[1]) or None,
            departure_date=parse_date(cells[2].text(strip=True)),
            departure_port=cells[3].text(strip=True) or None,
            arrival_date=parse_date(cells[4].text(strip=True)),
            arrival_port=cells[5].text(strip=True) or None,
            days_at_sea=int(days_match.group(1)) if days_match else None,
            tonnage=int(tonnage_text.replace(",", "")) if tonnage_text else None,
            detail_url=detail_url,
        ))
    return summaries


def fetch_patrol_list(client: PoliteHttpClient, slug: str) -> list[PatrolSummary]:
    url = f"{BASE_URL}/boats/patrols/{slug}.html"
    html = client.get_text(url)
    return parse_patrol_list(html, url)

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_date
from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import PatrolSummary

_DAYS_RE = re.compile(r"(\d+)")
_INT_RE = re.compile(r"\d+")


def _int_or_none(text: str | None) -> int | None:
    if not text:
        return None
    match = _INT_RE.search(text.replace(",", ""))
    return int(match.group()) if match else None


def parse_patrol_list(html: str, page_url: str) -> list[PatrolSummary]:
    parser = HTMLParser(html)
    table = parser.css_first("table.table_subtle")
    if table is None:
        return []

    summaries = []
    seen_external_ids = set()
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

        # A patrol split over several entries links the same page from each row
        # (the later ones carry a glyph instead of a number). The patrol is stored
        # once, by its first entry.
        if external_id in seen_external_ids:
            continue
        seen_external_ids.add(external_id)

        days_text = cells[6].text(strip=True)
        days_match = _DAYS_RE.match(days_text)

        tonnage_text = cells[7].text(strip=True)

        patrol_number = _int_or_none(cells[0].text(strip=True))
        if patrol_number is None:
            patrol_number = len(summaries) + 1

        summaries.append(PatrolSummary(
            external_id=external_id,
            patrol_number=patrol_number,
            commander=clean_text(cells[1]) or None,
            departure_date=parse_date(cells[2].text(strip=True)),
            departure_port=cells[3].text(strip=True) or None,
            arrival_date=parse_date(cells[4].text(strip=True)),
            arrival_port=cells[5].text(strip=True) or None,
            days_at_sea=int(days_match.group(1)) if days_match else None,
            tonnage=_int_or_none(tonnage_text),
            detail_url=detail_url,
        ))
    return summaries


def fetch_patrol_list(client: PoliteHttpClient, slug: str) -> list[PatrolSummary]:
    url = f"{BASE_URL}/boats/patrols/{slug}.html"
    html = client.get_text(url)
    return parse_patrol_list(html, url)

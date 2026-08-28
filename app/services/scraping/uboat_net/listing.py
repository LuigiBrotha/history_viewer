import re

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.http_client import BASE_URL, PoliteHttpClient
from app.services.scraping.uboat_net.types import BoatRef

_SLUG_RE = re.compile(r"^/boats/(u\d+)\.htm$")


def parse_listing(html: str) -> list[BoatRef]:
    parser = HTMLParser(html)
    seen: dict[str, BoatRef] = {}
    for anchor in parser.css("a[href]"):
        href = anchor.attributes.get("href") or ""
        match = _SLUG_RE.match(href)
        if not match:
            continue
        slug = match.group(1)
        if slug in seen:
            continue
        seen[slug] = BoatRef(slug=slug, number=anchor.text(strip=True))
    return list(seen.values())


def fetch_listing(client: PoliteHttpClient) -> list[BoatRef]:
    html = client.get_text(f"{BASE_URL}/boats/listing.html")
    return parse_listing(html)

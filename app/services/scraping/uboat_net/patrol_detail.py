import re

from selectolax.parser import HTMLParser

from app.services.scraping.uboat_net.dates import parse_iso_date
from app.services.scraping.uboat_net.http_client import PoliteHttpClient
from app.services.scraping.uboat_net.text import clean_text
from app.services.scraping.uboat_net.types import PatrolDetail, RoutePointData

_COORDS_BLOCK_RE = re.compile(r"patrolRouteCoordinates\s*=\s*\[(.*?)\];", re.DOTALL)
_COORD_PAIR_RE = re.compile(r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]")
_DAILY_LINK_RE = re.compile(r'href="/boats/patrols/[^/"]+/(\d{4}-\d{2}-\d{2})\.html"')


def parse_patrol_detail(html: str) -> PatrolDetail:
    parser = HTMLParser(html)
    description_node = parser.css_first(".emphasis p")
    description = clean_text(description_node) or None if description_node else None

    coords_match = _COORDS_BLOCK_RE.search(html)
    coord_pairs = _COORD_PAIR_RE.findall(coords_match.group(1)) if coords_match else []
    # Only look for daily-position links after the coordinates block: those are
    # the ones the spec's ordered-zip actually pairs with the route polyline. A
    # date-shaped link appearing earlier in the page (e.g. in unrelated nav/body
    # content) must not be picked up here.
    dates = _DAILY_LINK_RE.findall(html[coords_match.end():]) if coords_match else []

    # Per spec: if the two ordered lists don't line up in length, don't guess —
    # store every point in this patrol with date = NULL rather than zipping only
    # the first N and leaving the remainder undated.
    dates_match_coords = len(dates) == len(coord_pairs)

    points = []
    for index, (lat, lng) in enumerate(coord_pairs):
        point_date = parse_iso_date(dates[index]) if dates_match_coords else None
        points.append(RoutePointData(sequence=index, lat=float(lat), lng=float(lng), date=point_date))

    return PatrolDetail(description=description, route_points=points)


def fetch_patrol_detail(client: PoliteHttpClient, url: str) -> PatrolDetail:
    html = client.get_text(url)
    return parse_patrol_detail(html)

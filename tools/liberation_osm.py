"""Bevrijdingen for the countries no Wikipedia list or article covers.

- Denmark: the liberation stones (befrielsessten) of OpenStreetMap, which name 4 or 5 May 1945; each
  stands in a village, named after the nearest place in OpenStreetMap. Two Overpass queries, cached.
  The capitulation in Denmark took effect on the morning of 5 May; Bornholm was the Red Army's,
  on 9 May.
- Norway, Slovenia and Estonia: their capital and largest towns on the country's day of liberation,
  positioned by their English Wikipedia article (one request).
"""

import json
import math
import re
import time
import urllib.parse
import urllib.request

from tools import liberations as lists
from tools.liberations import Bevrijding

OVERPASS = "https://overpass-api.de/api/interpreter"

MEMORIALS_QUERY = """[out:json][timeout:300];
area["ISO3166-1"="DK"][admin_level=2]->.c;
nwr(area.c)["historic"~"^(memorial|monument)$"][~"^(name|inscription|description|memorial:text)$"~"befri",i];
out center tags;"""

PLACES_QUERY = """[out:json][timeout:180];
area["ISO3166-1"="DK"][admin_level=2]->.dk;
node(area.dk)["place"~"^(city|town|village|hamlet|suburb)$"]["name"];
out body;"""

DENMARK = (54.5, 57.8, 8.0, 15.2)
BORNHOLM_WEST = 14.6
DANISH_DAY = re.compile(r"\b0?([45])\.?\s*(?:maj|mai|may)\s*1945|\b0?([45])[./-]\s?0?5[./-]\s?1945", re.IGNORECASE)

# The capital and largest towns of the countries without a list: (English article, Dutch name,
# country, liberated, occupied or None, Kamp).
TOWNS = [
    ("Oslo", "Oslo", "Noorwegen", "1945-05-08", "1940-04-09", "westers"),
    ("Bergen", "Bergen", "Noorwegen", "1945-05-08", "1940-04-09", "westers"),
    ("Trondheim", "Trondheim", "Noorwegen", "1945-05-08", "1940-04-09", "westers"),
    ("Stavanger", "Stavanger", "Noorwegen", "1945-05-08", "1940-04-09", "westers"),
    ("Kirkenes", "Kirkenes", "Noorwegen", "1944-10-25", "1940-04-09", "sovjet"),
    ("Ljubljana", "Ljubljana", "Joegoslavië", "1945-05-09", "1941-04-11", "westers"),
    ("Maribor", "Maribor", "Joegoslavië", "1945-05-09", "1941-04-08", "westers"),
    ("Tallinn", "Tallinn", "Sovjet-Unie", "1944-09-22", "1941-08-28", "sovjet"),
    ("Tartu", "Tartu", "Sovjet-Unie", "1944-08-25", "1941-07-25", "sovjet"),
]


def overpass(query, name):
    """The answer to an Overpass query, cached as `name` in the liberations cache."""
    path = lists.CACHE / name
    if path.exists():
        return json.loads(path.read_text())
    body = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(OVERPASS, data=body, headers={"User-Agent": lists.USER_AGENT})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=400) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except (urllib.error.HTTPError, json.JSONDecodeError):
            # Overpass answers 429 or 504 when it is busy: wait longer each time.
            if attempt == 5:
                raise
            time.sleep(30 * (attempt + 1))
    lists.CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _km(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _point(element):
    return (element.get("lat") or element["center"]["lat"], element.get("lon") or element["center"]["lon"])


def denmark_stones(memorials, places):
    """One Bevrijding per Danish place with a liberation stone that names 4 or 5 May 1945, named
    after the nearest place within 5 km; Bornholm's on 9 May, by the Red Army."""
    south, north, west, east = DENMARK
    named = [(_point(p), p["tags"]["name"]) for p in places if "lat" in p]
    found, seen = [], set()
    for element in memorials:
        tags = element.get("tags", {})
        text = " ".join(tags.get(k, "") for k in ("name", "inscription", "description", "memorial:text"))
        if not DANISH_DAY.search(text):
            continue
        point = _point(element)
        if not (south <= point[0] <= north and west <= point[1] <= east):
            continue
        near = min(named, key=lambda p: _km(point, p[0]), default=None)
        if near is None or _km(point, near[0]) > 5 or near[1] in seen:
            continue
        seen.add(near[1])
        bornholm = point[1] > BORNHOLM_WEST
        b = Bevrijding(
            place=near[1], title=None, lang="da", country="Denemarken",
            liberated="1945-05-09" if bornholm else "1945-05-05", occupied="1940-04-09",
            lat=round(near[0][0], 5), lng=round(near[0][1], 5), source="osm-dk",
        )
        b.name = near[1]
        b.kamp = "sovjet" if bornholm else "westers"
        b.date_text = "bevrijdingssteen" if not bornholm else "bevrijdingssteen; Bornholm door het Rode Leger"
        found.append(b)
    return found


def towns():
    """The capitals and largest towns of Norway, Slovenia and Estonia on their day of liberation."""
    known = lists.lookup("en", [title for title, *_ in TOWNS])
    found = []
    for title, name, country, liberated, occupied, kamp in TOWNS:
        entry = known.get(title, {})
        if "lat" not in entry:
            continue
        b = Bevrijding(
            place=name, title=title, lang="en", country=country, liberated=liberated, occupied=occupied,
            lat=entry["lat"], lng=entry["lng"], source="landdatum",
        )
        b.name = name
        b.kamp = kamp
        found.append(b)
    return found


def harvest(listed):
    """Denmark's stones and the towns, without a place a list or an article already has."""
    from tools.liberation_articles import already_listed

    memorials = overpass(MEMORIALS_QUERY, "osm-dk-memorials.json")["elements"]
    places = overpass(PLACES_QUERY, "osm-dk-places.json")["elements"]
    found = denmark_stones(memorials, places) + towns()
    return [b for b in found if not already_listed(b, listed)]

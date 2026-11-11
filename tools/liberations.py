"""Bevrijdingen: when a place was liberated (and, where known, occupied), from three list articles.

- nl: "Chronologisch overzicht van de bevrijding van Nederlandse plaatsen in de Tweede
  Wereldoorlog": a liberation date, the province and who liberated the place.
- ru: "Список городов СССР, оккупированных и освобождённых во время Великой Отечественной
  войны": occupation and liberation date, the troops and the operation, per Soviet town.
- ru: "Список зарубежных городов, освобождённых Советской Армией…": the date the Soviet Army
  took a town abroad, per country.

Three requests fetch the lists; the coordinates of their places take one request per 50 places
(MediaWiki's limit), plus one per 50 for the few places that only Wikidata places.

    poetry run python -m tools.liberations [--output frontend/battles/bevrijdingen.json] [--refresh]
"""

import argparse
from collections import Counter
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

USER_AGENT = "uboats-liberations/1.0 (WWII map; batch requests)"
CACHE = Path.home() / ".cache" / "uboats" / "liberations"
BATCH = 50
PAUSE = 2.0
ATTEMPTS = 8

NL_LIST = "Chronologisch overzicht van de bevrijding van Nederlandse plaatsen in de Tweede Wereldoorlog"
RU_USSR = "Список городов СССР, оккупированных и освобождённых во время Великой Отечественной войны"
RU_ABROAD = "Список зарубежных городов, освобождённых Советской Армией во время Великой Отечественной войны"
FR_LIST = "Chronologie de la Libération en France"
BE_ARTICLE = "Bevrijding van de Duitse bezetting in België (Tweede Wereldoorlog)"

# The lists, by the key each Bevrijding names as its source.
LISTS = {"nl": ("nl", NL_LIST), "ru-ussr": ("ru", RU_USSR), "ru-abroad": ("ru", RU_ABROAD),
         "fr": ("fr", FR_LIST), "nl-be": ("nl", BE_ARTICLE)}

# Rough bounds per country (south, north, west, east), wide enough for the borders of 1939–1945;
# a place outside them got the article of a namesake elsewhere and keeps no position.
BOUNDS = {
    "Nederland": (50.7, 53.6, 3.3, 7.3), "Frankrijk": (41.3, 51.2, -5.2, 9.6), "België": (49.4, 51.6, 2.5, 6.5),
    "Sovjet-Unie": (38.0, 70.0, 20.0, 180.0),
    "Polen": (48.9, 55.0, 14.0, 24.2), "Duitsland": (50.0, 55.5, 9.0, 23.0),
    "Hongarije": (45.7, 48.6, 16.0, 22.9), "Tsjechoslowakije": (47.7, 51.1, 12.0, 24.7),
    "Roemenië": (43.6, 48.3, 20.2, 29.8), "Oostenrijk": (46.3, 49.1, 9.5, 17.2),
    "China": (18.0, 54.0, 73.0, 135.0), "Korea": (33.0, 43.1, 124.0, 131.0),
    "Bulgarije": (41.2, 44.3, 22.3, 28.7), "Noorwegen": (57.0, 71.5, 4.0, 31.5),
    "Joegoslavië": (40.8, 46.9, 13.3, 23.1),
}


def within(country, lat, lng):
    south, north, west, east = BOUNDS[country]
    return south <= lat <= north and west <= lng <= east


# Poland between the wars, roughly (lat, lng): the list sorts towns by today's borders, so
# Breslau, Stettin and Danzig stand under Poland, but they were German and were taken, not
# liberated. Fine enough for the towns of the list, not for a border village.
INTERWAR_POLAND = [
    (54.83, 18.05), (54.80, 18.60), (54.45, 18.58), (54.25, 18.55), (54.00, 18.85), (53.30, 19.50),
    (53.20, 20.50), (53.30, 21.50), (53.50, 22.50), (54.35, 22.80), (54.30, 23.50), (55.30, 25.80),
    (55.90, 26.70), (55.60, 28.10), (54.60, 27.80), (53.70, 27.00), (52.70, 26.90), (51.80, 27.50),
    (50.60, 27.20), (49.50, 26.20), (48.55, 26.20), (48.30, 25.30), (48.00, 24.90), (48.40, 23.60),
    (48.90, 22.80), (49.10, 22.60), (49.40, 21.30), (49.40, 20.00), (49.60, 19.20), (49.80, 18.80),
    (50.00, 18.55), (50.25, 18.85), (50.50, 19.00), (50.80, 18.70), (51.00, 18.40), (51.30, 18.00),
    (51.60, 17.20), (51.70, 16.60), (52.10, 16.00), (52.50, 15.95), (52.90, 16.10), (53.05, 16.80),
    (53.40, 17.20), (53.70, 17.45), (54.15, 17.75), (54.55, 17.55), (54.60, 17.95),
]


def inside(polygon, lat, lng):
    """Point in polygon by ray casting."""
    result = False
    for (lat1, lng1), (lat2, lng2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (lat1 > lat) != (lat2 > lat):
            if lng < lng1 + (lat - lat1) * (lng2 - lng1) / (lat2 - lat1):
                result = not result
    return result


def wartime_country(country, lat, lng):
    """(country, verb) as during the war, for a town the list sorts by today's borders: a Polish
    town outside interwar Poland was German, a Czechoslovak one in Slovakia lay in an Axis state;
    both were taken, not liberated."""
    if country == "Polen" and not inside(INTERWAR_POLAND, lat, lng):
        return "Duitsland", "ingenomen"
    # The border of Moravia and Slovakia, as a line from (48.6, 17.0) to (49.5, 18.8).
    if country == "Tsjechoslowakije" and lat < 49.6 and lng > 17.0 + (lat - 48.6) * 2.0:
        return "Slowakije", "ingenomen"
    return None


# The country sections of the list of towns abroad, in Dutch; the Axis countries were taken,
# not liberated.
ABROAD = {
    "Австрия": ("Oostenrijk", "ingenomen"),
    "Болгария": ("Bulgarije", "ingenomen"),
    "Венгрия": ("Hongarije", "ingenomen"),
    "ГДР": ("Duitsland", "ingenomen"),
    "Норвегия": ("Noorwegen", "bevrijd"),
    "Польша": ("Polen", "bevrijd"),
    "Румыния": ("Roemenië", "ingenomen"),
    "Чехословакия": ("Tsjechoslowakije", "bevrijd"),
    "Югославия": ("Joegoslavië", "bevrijd"),
    "КНР": ("China", "bevrijd"),
    "КНДР": ("Korea", "bevrijd"),
}

NL_MONTHS = {m: i for i, m in enumerate(
    "januari februari maart april mei juni juli augustus september oktober november december".split(), 1)}
RU_MONTHS = {m: i for i, m in enumerate(
    "января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split(), 1)}


@dataclass
class Bevrijding:
    place: str            # the name as the list shows it
    title: str | None     # the article of the place, if the list links one
    lang: str             # the Wikipedia the list (and the title) comes from
    country: str          # Dutch name of the country the place lay in, as the list groups it
    liberated: str        # ISO date
    verb: str = "bevrijd"  # "bevrijd", or "ingenomen" for a town in an Axis country
    occupied: str | None = None
    date_text: str | None = None  # the list's own words when they are more than one plain date
    by: str | None = None          # who liberated it, as the list names them
    operation: str | None = None   # the article of the operation, in the list's language
    operation_en: str | None = None  # the English article on the same operation, if there is one
    partial: bool = False          # only part of the town was occupied
    lat: float | None = None
    lng: float | None = None
    source: str = ""              # which list: a key of LISTS
    name: str = ""                # the name on the map: Dutch, else English, else transliterated
    kamp: str | None = None       # who liberated it, when the source does not say it already


# --- Wikitext ------------------------------------------------------------------------------

REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.DOTALL | re.IGNORECASE)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LINK = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]*))?\]\]")


def strip_refs(text):
    return REF.sub("", COMMENT.sub("", text))


def _depth_scan(text):
    """Yield (index, char, depth) with depth the nesting of {{ }} and [[ ]] before the char."""
    depth = 0
    i = 0
    while i < len(text):
        pair = text[i:i + 2]
        if pair in ("{{", "[["):
            yield i, pair, depth
            depth += 1
            i += 2
            continue
        if pair in ("}}", "]]") and depth > 0:
            depth -= 1
            yield i, pair, depth
            i += 2
            continue
        yield i, text[i], depth
        i += 1


def _split_top(text, sep="|"):
    """Split on `sep` outside templates and links."""
    parts, start = [], 0
    for i, char, depth in _depth_scan(text):
        if char == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _cell_content(cell):
    """Split a cell into (attributes, content): `style="…" | text` has attributes."""
    parts = _split_top(cell)
    if len(parts) > 1 and "=" in parts[0] and "[[" not in parts[0] and "{{" not in parts[0]:
        return parts[0].strip(), "|".join(parts[1:]).strip()
    return "", cell.strip()


@dataclass
class Table:
    section: str
    rows: list = field(default_factory=list)  # each row: (row attributes, [cells])


def tables(wikitext):
    """Every table of the page with its rows, rowspans spread over the rows they cover.

    Only lines that begin a table, row or cell outside any template count, so templates that
    run over several lines (a hidden list of troops) stay inside their cell.
    """
    text = strip_refs(wikitext)
    lines, buffer, depth = [], [], 0
    for line in text.split("\n"):
        if depth == 0 and buffer:
            lines.append("\n".join(buffer))
            buffer = []
        buffer.append(line)
        depth += line.count("{{") + line.count("[[") - line.count("}}") - line.count("]]")
        depth = max(depth, 0)
    if buffer:
        lines.append("\n".join(buffer))

    found, current, section, row, row_attrs = [], None, "", None, ""
    spans = {}  # column → [rows left, content]

    def close_row():
        nonlocal row
        if current is None or row is None:
            return
        cells, column, index = [], 0, 0
        while index < len(row) or column in spans:
            if column in spans:
                left, content = spans[column]
                cells.append(content)
                if left <= 1:
                    del spans[column]
                else:
                    spans[column] = [left - 1, content]
            else:
                attrs, content = row[index]
                index += 1
                cells.append(content)
                match = re.search(r'rowspan\s*=\s*"?(\d+)', attrs)
                if match and int(match.group(1)) > 1:
                    spans[column] = [int(match.group(1)) - 1, content]
            column += 1
        if cells:
            current.rows.append((row_attrs, cells))
        row = None

    for block in lines:
        stripped = block.lstrip()
        if stripped.startswith("==") and current is None:
            section = stripped.strip("= \n")
        elif stripped.startswith("{|"):
            current = Table(section)
            row, row_attrs, spans = None, "", {}
        elif current is None:
            continue
        elif stripped.startswith("|}"):
            close_row()
            found.append(current)
            current = None
        elif stripped.startswith("|-"):
            close_row()
            row, row_attrs = [], stripped[2:].strip()
        elif stripped.startswith("!"):
            continue
        elif stripped.startswith("|"):
            if row is None:
                row, row_attrs = [], ""
            for cell in _split_top(stripped[1:].replace("||", "\u0000"), "\u0000"):
                row.append(_cell_content(cell))
        elif row:
            attrs, content = row[-1]
            row[-1] = (attrs, content + "\n" + block)
    return found


def plain(text):
    """Wikitext to plain text: link labels, no bold or italics, no templates or markup."""
    text = LINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def first_link(text):
    match = LINK.search(text)
    if not match:
        return None
    target = match.group(1).split("#")[0].strip()
    return target[0].upper() + target[1:] if target else None


# --- Dates ---------------------------------------------------------------------------------

def parse_date(text, months, year=None):
    """The date in `text` as ISO, with the year of the text or else `year`.

    Of two days ("3 of 4 oktober 1944", "nacht van 28-29 oktober") the last counts: by then the
    place was surely liberated. The second needs the year of the row above it. Returns None when
    there is no day and month.
    """
    words = plain(text).lower().replace(" ", " ")
    month_pattern = "|".join(months)
    match = re.search(rf"(\d{{1,2}})\D{{0,12}}?\b({month_pattern})\b(?:\s+(\d{{4}}))?", words)
    if not match:
        return None
    later_year = re.search(r"\b(19[34]\d)\b", words[match.start():])
    found_year = match.group(3) or (later_year.group(1) if later_year else None) or year
    if found_year is None:
        return None
    return f"{int(found_year):04d}-{months[match.group(2)]:02d}-{int(match.group(1)):02d}"


def _plain_date(text):
    """True when the cell is one date and nothing else, so the record needs no date_text."""
    # "г." (год), also as "г," or the Ukrainian "р.", is only the word "year".
    return re.fullmatch(r"\d{1,2} \S+ \d{4}( [гр]\.?,?| года)?", plain(text)) is not None


# --- The three lists -----------------------------------------------------------------------

def parse_nl(wikitext):
    source = "nl"
    found, year = [], None
    for table in tables(wikitext):
        for _, cells in table.rows:
            if len(cells) < 3:
                continue
            date_cell, _province, place_cell = cells[0], cells[1], cells[2]
            by = plain(cells[4]) if len(cells) > 4 else ""
            liberated = parse_date(date_cell, NL_MONTHS, year)
            if liberated is None or not plain(place_cell):
                continue
            year = liberated[:4]
            found.append(Bevrijding(
                place=plain(place_cell),
                title=first_link(place_cell),
                lang="nl",
                country="Nederland",
                liberated=liberated,
                date_text=None if _plain_date(date_cell) else plain(date_cell),
                by=by or None,
                source=source,
            ))
    return found


def _troops(cell):
    """The fronts (or fleets) of a cell of troops: the top level of the list, without armies."""
    text = re.sub(r"\{\{\s*Скрытый.*?Содержание\s*=", "", cell, flags=re.DOTALL)
    names = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("|"):
            continue
        for match in LINK.finditer(line.split(":")[0].split(" - ")[0].split(" — ")[0]):
            name = match.group(1).split("#")[0].strip()
            if name not in names:
                names.append(name)
    return ", ".join(dict.fromkeys(dutch_troops(n) for n in names)) or None


ORDINAL_FRONT = re.compile(r"^(\d)-й (Украинский|Белорусский|Прибалтийский|Дальневосточный) фронт")
FRONT_WORDS = {"Украинский": "Oekraïense", "Белорусский": "Wit-Russische", "Прибалтийский": "Baltische",
               "Дальневосточный": "Verre-Oostenfront"}
NAMED = {
    "Юго-Западный фронт": "Zuidwestfront", "Западный фронт": "Westfront", "Южный фронт": "Zuidfront",
    "Ленинградский фронт": "Leningradfront", "Воронежский фронт": "Voronezjfront", "Брянский фронт": "Brjanskfront",
    "Закавказский фронт": "Transkaukasusfront", "Центральный фронт": "Centrale Front",
    "Калининский фронт": "Kalininfront", "Степной фронт": "Steppefront", "Карельский фронт": "Karelische Front",
    "Северо-Кавказский фронт": "Noord-Kaukasusfront", "Забайкальский фронт": "Transbaikalfront",
    "Волховский фронт": "Wolchovfront", "Донской фронт": "Donfront", "Северо-Западный фронт": "Noordwestfront",
    "Белорусский фронт": "Wit-Russische Front", "Сталинградский фронт": "Stalingradfront",
    "Резервный фронт": "Reservefront", "Приморская армия": "Kustleger",
    "Черноморский флот": "Zwarte Zeevloot", "Балтийский флот": "Baltische Vloot", "Северный флот": "Noordelijke Vloot",
    "Тихоокеанский флот": "Pacifische Vloot", "Дунайская военная флотилия": "Donauflottielje",
    "Азовская военная флотилия": "Azovflottielje", "Днепровская военная флотилия": "Dnjeprflottielje",
    "ДнВФл": "Dnjeprflottielje", "Амурская военная флотилия": "Amoerflottielje",
    "Онежская военная флотилия": "Onegaflottielje", "Авиация дальнего действия": "Langeafstandsluchtmacht",
    "АДД": "Langeafstandsluchtmacht", "НОАЮ": "Joegoslavisch Volksbevrijdingsleger",
}


def dutch_troops(name):
    """A Soviet front, fleet or flotilla in Dutch; smaller units keep their Russian name."""
    match = ORDINAL_FRONT.match(name)
    if match:
        word = FRONT_WORDS[match.group(2)]
        return f"{match.group(1)}e {word}" if word.endswith("front") else f"{match.group(1)}e {word} Front"
    for russian, dutch in NAMED.items():
        if name.startswith(russian):
            return dutch
    return re.sub(r"\s*\(.*\)$", "", name)


def parse_ru_ussr(wikitext):
    source = "ru-ussr"
    found = []
    for table in tables(wikitext):
        for attrs, cells in table.rows:
            if len(cells) < 3:
                continue
            place_cell, occupied_cell, liberated_cell = cells[0], cells[1], cells[2]
            liberated = parse_date(liberated_cell, RU_MONTHS)
            if liberated is None or not plain(place_cell):
                continue
            occupied = parse_date(occupied_cell, RU_MONTHS)
            found.append(Bevrijding(
                place=plain(place_cell),
                title=first_link(place_cell),
                lang="ru",
                country="Sovjet-Unie",
                liberated=liberated,
                occupied=occupied,
                date_text=None if _plain_date(liberated_cell) else plain(liberated_cell),
                by=_troops(cells[3]) if len(cells) > 3 else None,
                operation=first_link(cells[4]) if len(cells) > 4 else None,
                partial="FFDDDD" in attrs.upper(),
                source=source,
            ))
    return found


def parse_ru_abroad(wikitext):
    source = "ru-abroad"
    found = []
    for table in tables(wikitext):
        country, verb = next(
            ((dutch, verb) for name, (dutch, verb) in ABROAD.items() if name in table.section), (None, None))
        if country is None:
            continue
        for _, cells in table.rows:
            if len(cells) < 2:
                continue
            place_cell, taken_cell = cells[0], cells[1]
            liberated = parse_date(taken_cell, RU_MONTHS)
            if liberated is None or not plain(place_cell):
                continue
            found.append(Bevrijding(
                place=plain(place_cell),
                title=first_link(place_cell),
                lang="ru",
                country=country,
                liberated=liberated,
                verb=verb,
                date_text=None if _plain_date(taken_cell) else plain(taken_cell),
                by=_troops(cells[2]) if len(cells) > 2 else None,
                operation=first_link(cells[3]) if len(cells) > 3 else None,
                source=source,
            ))
    return found


# --- Requests ------------------------------------------------------------------------------

def _get(url, params=None):
    """GET, or POST for the APIs: 50 Cyrillic titles make a URL too long (HTTP 414)."""
    body = None
    if params and url.endswith("api.php"):
        body = urllib.parse.urlencode(params).encode()
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    for attempt in range(ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == ATTEMPTS - 1:
                raise
            # Wait as long as the server asks, a little longer each time.
            wait = float(error.headers.get("Retry-After") or 5)
            print(f"{error.code}, wacht {wait + 2 * attempt:.0f} s", file=sys.stderr)
            time.sleep(wait + 2 * attempt)
    raise RuntimeError("unreachable")


def fetch_list(lang, title, refresh=False):
    """The raw wikitext of a list article, kept in the cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{lang}-{urllib.parse.quote(title, safe='')[:120]}.txt"
    if path.exists() and not refresh:
        return path.read_text()
    text = _get(f"https://{lang}.wikipedia.org/w/index.php", {"title": title, "action": "raw", "redirect": "yes"})
    if text.lstrip().upper().startswith("#REDIRECT") or text.lstrip().startswith("#перенаправление"):
        target = first_link(text)
        text = _get(f"https://{lang}.wikipedia.org/w/index.php", {"title": target, "action": "raw"})
    path.write_text(text)
    time.sleep(PAUSE)
    return text


def lookup(lang, titles):
    """{title: {"lat", "lng", "nl", "en"}} for article titles, as far as known.

    One request per 50 titles gives each article's coordinates and Wikidata item (following
    redirects; a disambiguation page counts as unknown), one per 50 items its Dutch and English
    name and the coordinates for an article without its own. Everything found is kept in the
    cache, so a rerun asks only for new titles.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"places-{lang}.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    titles = sorted(set(titles) - set(cached))
    found, items = {}, {}
    for start in range(0, len(titles), BATCH):
        chunk = titles[start:start + BATCH]
        data = json.loads(_get(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "prop": "coordinates|pageprops", "ppprop": "wikibase_item|disambiguation",
            "colimit": "max", "titles": "|".join(chunk),
        }))
        query = data.get("query", {})
        alias = {}
        for kind in ("normalized", "redirects"):
            for entry in query.get(kind, []):
                alias[entry["from"]] = entry["to"]
        pages = {page["title"]: page for page in query.get("pages", [])}
        for title in chunk:
            name = title
            while name in alias:
                name = alias[name]
            page = pages.get(name)
            found[title] = {}
            if page is None or page.get("missing") or "disambiguation" in page.get("pageprops", {}):
                continue
            if page.get("coordinates"):
                point = page["coordinates"][0]
                found[title].update(lat=round(point["lat"], 5), lng=round(point["lon"], 5))
            item = page.get("pageprops", {}).get("wikibase_item")
            if item:
                items.setdefault(item, []).append(title)
        time.sleep(PAUSE)
    ids = sorted(items)
    for start in range(0, len(ids), BATCH):
        chunk = ids[start:start + BATCH]
        data = json.loads(_get("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "format": "json", "props": "claims|labels",
            "languages": "nl|en", "ids": "|".join(chunk),
        }))
        for item, entity in data.get("entities", {}).items():
            names = {code: label["value"] for code, label in entity.get("labels", {}).items()}
            point = None
            for claim in entity.get("claims", {}).get("P625", [])[:1]:
                point = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            for title in items.get(item, []):
                found[title].update({code: names[code] for code in ("nl", "en") if code in names})
                if point and "lat" not in found[title]:
                    found[title].update(lat=round(point["latitude"], 5), lng=round(point["longitude"], 5))
        time.sleep(PAUSE)
    if found:
        cached.update(found)
        path.write_text(json.dumps(cached, ensure_ascii=False, indent=0))
    return cached


CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "jo", "ж": "zj", "з": "z",
    "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "oe", "ф": "f", "х": "ch", "ц": "ts", "ч": "tsj", "ш": "sj",
    "щ": "sjtsj", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "joe", "я": "ja",
    "і": "i", "ї": "ji", "є": "je", "ґ": "g",
}


def transliterate(name):
    """Russian in Dutch letters (Жлобин → Zjlobin, Чугуев → Tsjoegoejev), for a place no Wikidata
    name covers. An е at the start of a word or after a vowel is "je", as in Dutch spelling."""
    out, previous = [], ""
    for char in name:
        lower = char.lower()
        latin = CYRILLIC.get(lower)
        if lower == "е" and (not previous.isalpha() or previous in "аеёиоуыэюяіїє"):
            latin = "je"
        previous = lower
        if latin is None:
            out.append(char)
        else:
            out.append(latin.capitalize() if char.isupper() else latin)
    return "".join(out)


def dutch_name(b, known):
    """The name the map shows: Dutch, else English (Wikidata), else the list's own spelling."""
    if b.lang == "nl":
        return b.place
    # Only the article whose position lies in the country is the place itself; a namesake
    # elsewhere (Пуппен → "YouTube Poop") lends no name.
    if b.lat is None:
        return transliterate(b.place)
    entry = known.get(b.title or b.place, {})
    return entry.get("nl") or entry.get("en") or transliterate(b.place)


def english_titles(lang, titles):
    """{title: English article title or None}, from the language links, 50 titles per request,
    following redirects; cached like `lookup`."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"english-{lang}.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    titles = sorted(set(titles) - set(cached))
    for start in range(0, len(titles), BATCH):
        chunk = titles[start:start + BATCH]
        data = json.loads(_get(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "prop": "langlinks", "lllang": "en", "lllimit": "max", "titles": "|".join(chunk),
        }))
        query = data.get("query", {})
        alias = {}
        for kind in ("normalized", "redirects"):
            for entry in query.get(kind, []):
                alias[entry["from"]] = entry["to"]
        pages = {page["title"]: page for page in query.get("pages", [])}
        for title in chunk:
            name = title
            while name in alias:
                name = alias[name]
            links = pages.get(name, {}).get("langlinks", [])
            cached[title] = links[0]["title"] if links else None
        time.sleep(PAUSE)
    if titles:
        path.write_text(json.dumps(cached, ensure_ascii=False, indent=0))
    return cached


FR_DATE = re.compile(r"\{\{\s*date-?\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*\|\s*(\d{4})")
# The free zone of Vichy France, roughly (lat, lng), from the Pyrenees west of Orthez along the
# demarcation line past Angoulême, Vierzon, Moulins and Chalon to Geneva, then the Alps, the
# Mediterranean coast and the Pyrenees. The north and the Atlantic coast were occupied from
# May 1940, the free zone from 11 November 1942 (Case Anton), Corsica by Italy from then too.
FREE_ZONE = [
    (43.20, -1.00), (43.60, -0.70), (44.30, -0.20), (45.00, 0.00), (45.60, 0.20), (46.20, 0.60),
    (46.60, 1.50), (47.20, 2.10), (46.60, 3.30), (46.80, 4.80), (46.40, 5.60), (46.20, 6.10),
    (45.90, 6.90), (45.10, 6.70), (44.10, 7.70), (43.75, 7.50), (43.00, 6.00), (43.30, 4.00),
    (42.50, 3.20), (42.40, 1.50), (42.70, 0.00), (43.00, -0.70),
]
FRANCE_INVADED = "1940-05-10"
CASE_ANTON = "1942-11-11"


def french_occupation(lat, lng):
    """When the Germans (or, on Corsica, the Italians) occupied a place in France."""
    if lng > 8.0 or inside(FREE_ZONE, lat, lng):
        return CASE_ANTON
    return FRANCE_INVADED


def _next_day(iso):
    import datetime as dt
    return (dt.date.fromisoformat(iso) + dt.timedelta(days=1)).isoformat()


FR_ORDINAL = re.compile(r"\{\{\s*(\d+(?:e|er|re|ère))\s*(?:\|([^{}|]*))?\}\}")
FR_NATIONS = {"française": "Frans", "françaises": "Frans", "américaine": "Amerikaans", "américaines": "Amerikaans",
              "britannique": "Brits", "britanniques": "Brits", "canadienne": "Canadees", "polonaise": "Pools",
              "belge": "Belgisch", "et": "en", "résistance": "verzet", "fFI": "FFI"}


def french_liberators(cell):
    """The liberators in Dutch words where it is simple: "Française : 73e goum" → "Frans: 73e goum"."""
    text = plain(FR_ORDINAL.sub(lambda m: f"{m.group(1)} {m.group(2) or ''}".strip(), cell)).rstrip(" .")
    head, colon, rest = text.partition(":")
    if not colon:
        return text or None
    words = [FR_NATIONS.get(word.lower(), word) for word in re.split(r"[\s,]+", head.strip()) if word]
    rest = rest.strip(" ?")  # "?": the list does not know which units
    return f"{' '.join(words)}: {rest}" if rest else " ".join(words) or None


def parse_fr(wikitext):
    """The French chronology: a date (day, month and year in a template), the place and its
    liberators. A date in parentheses was a liberation the Germans undid (Tulle, 8 June 1944):
    it counts when the place has a later row, which then starts a new occupation the day after;
    without one (Nantua) the place has only its final liberation, and here none."""
    rows = []
    for table in tables(wikitext):
        for _, cells in table.rows:
            if len(cells) < 2:
                continue
            match = FR_DATE.search(cells[0])
            if not match or not plain(cells[1]):
                continue
            day, month, year = (int(g) for g in match.groups())
            rows.append((cells, f"{year:04d}-{month:02d}-{day:02d}", "(" in plain(cells[0]) or cells[0].strip().startswith("(")))
    found, temporary = [], {}
    for cells, liberated, undone in rows:
        title = first_link(cells[1])
        key = title or plain(cells[1])
        b = Bevrijding(
            place=plain(cells[1]),
            title=title,
            lang="fr",
            country="Frankrijk",
            liberated=liberated,
            by=french_liberators(cells[4]) if len(cells) > 4 else None,
            operation=first_link(cells[5]) if len(cells) > 5 else None,
            source="fr",
        )
        if undone:
            b.date_text = "tijdelijk, daarna weer bezet"
            temporary[key] = b
            continue
        if key in temporary:
            found.append(temporary.pop(key))
            b.occupied = _next_day(found[-1].liberated)
        found.append(b)
    return found


BE_EXCLUDE = {"Henegouwen", "Luxemburg (provincie)", "Tervurenlaan", "Albertkanaal", "Brigade Piron",
              "Bernard Montgomery", "Stadhuis van Brussel", "Fort van Breendonk"}


def parse_be(wikitext):
    """The Belgian article lists its liberations as bullets ("Op 4 september werd [[Antwerpen]]
    bevrijd, evenals …"); every place linked in such a line counts, 1944 being the year of all."""
    found = []
    for line in strip_refs(wikitext).split("\n"):
        if not line.startswith("* Op ") or not re.search(r"bevrijd|ingenomen", line):
            continue
        liberated = parse_date(line[:40], NL_MONTHS, "1944")
        if liberated is None:
            continue
        for match in LINK.finditer(line):
            target = match.group(1).split("#")[0].strip()
            label = (match.group(2) or target).strip()
            if target in BE_EXCLUDE:
                continue
            # A battle linked under the town's name ("[[Slag om Leuven (1944)|Leuven]]").
            title = label if target.startswith("Slag om") else target
            found.append(Bevrijding(
                place=re.sub(r"\s*\(.*\)$", "", label), title=title, lang="nl", country="België", liberated=liberated,
                occupied="1940-05-10", source="nl-be",
            ))
    return found


def drop_repeats(found):
    """Without a row the list repeats word for word (Havelte twice on 13 april 1945); the first
    keeps its place. Two places on one article (Cadier and Keer) both stay."""
    seen, kept = set(), []
    for b in found:
        key = (b.source, b.place, b.title, b.liberated, b.occupied)
        if key not in seen:
            seen.add(key)
            kept.append(b)
    return kept


def harvest(refresh=False):
    found = parse_nl(fetch_list("nl", NL_LIST, refresh))
    found += parse_ru_ussr(fetch_list("ru", RU_USSR, refresh))
    found += parse_ru_abroad(fetch_list("ru", RU_ABROAD, refresh))
    found += parse_fr(fetch_list("fr", FR_LIST, refresh))
    found += parse_be(fetch_list("nl", BE_ARTICLE, refresh))
    found = drop_repeats(found)
    for lang in ("nl", "ru", "fr"):
        known = lookup(lang, {b.title or b.place for b in found if b.lang == lang})
        for b in found:
            if b.lang != lang:
                continue
            entry = known.get(b.title or b.place, {})
            if "lat" in entry and within(b.country, entry["lat"], entry["lng"]):
                b.lat, b.lng = entry["lat"], entry["lng"]
                wartime = wartime_country(b.country, b.lat, b.lng)
                if wartime:
                    b.country, b.verb = wartime
                if b.source == "fr" and b.occupied is None:
                    b.occupied = french_occupation(b.lat, b.lng)
            b.name = dutch_name(b, known)
    # Most Veldslagen are English articles, so the operation also gets its English title.
    # Then the places only an article of their own covers, language by language.
    from tools import liberation_articles
    for rule in liberation_articles._rules().values():
        found += liberation_articles.harvest(rule, [b for b in found if b.lat is not None])
    for lang in ("ru", "fr"):
        english = english_titles(lang, {b.operation for b in found if b.lang == lang and b.operation})
        for b in found:
            if b.lang == lang and b.operation:
                b.operation_en = english.get(b.operation)
    found.sort(key=lambda b: (b.liberated, b.country, b.name))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", default="frontend/battles/bevrijdingen.json")
    parser.add_argument("--refresh", action="store_true", help="fetch the lists again instead of the cache")
    args = parser.parse_args(argv)
    found = harvest(args.refresh)
    records = [{k: v for k, v in asdict(b).items() if v not in (None, False)} for b in found]
    # One Bevrijding per line, so a rerun shows as a readable diff.
    lines = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records)
    Path(args.output).write_text("[\n" + lines + "\n]\n")
    placed = sum(1 for b in found if b.lat is not None)
    print(f"{len(found)} Bevrijdingen, {placed} met positie → {args.output}", file=sys.stderr)
    for source, count in sorted(Counter(b.source for b in found).items()):
        print(f"{source}: {count}", file=sys.stderr)
    for lang in ("nl", "ru", "fr"):
        missing = [b.name for b in found if b.lang == lang and b.lat is None]
        print(f"{lang}: {len(missing)} zonder positie: {', '.join(missing[:15])}", file=sys.stderr)


if __name__ == "__main__":
    main()

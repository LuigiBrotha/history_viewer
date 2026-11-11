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

# The lists, by the key each Bevrijding names as its source.
LISTS = {"nl": ("nl", NL_LIST), "ru-ussr": ("ru", RU_USSR), "ru-abroad": ("ru", RU_ABROAD)}

# Rough bounds per country (south, north, west, east), wide enough for the borders of 1939–1945;
# a place outside them got the article of a namesake elsewhere and keeps no position.
BOUNDS = {
    "Nederland": (50.7, 53.6, 3.3, 7.3), "Sovjet-Unie": (38.0, 70.0, 20.0, 180.0),
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
    partial: bool = False          # only part of the town was occupied
    lat: float | None = None
    lng: float | None = None
    source: str = ""              # which list: a key of LISTS
    name: str = ""                # the name on the map: Dutch, else English, else transliterated


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
    return re.fullmatch(r"\d{1,2} \S+ \d{4}( г\.?| года)?", plain(text)) is not None


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
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
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
    "і": "i", "ї": "ji", "є": "je",
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


def harvest(refresh=False):
    found = parse_nl(fetch_list("nl", NL_LIST, refresh))
    found += parse_ru_ussr(fetch_list("ru", RU_USSR, refresh))
    found += parse_ru_abroad(fetch_list("ru", RU_ABROAD, refresh))
    for lang in ("nl", "ru"):
        known = lookup(lang, {b.title or b.place for b in found if b.lang == lang})
        for b in found:
            if b.lang != lang:
                continue
            entry = known.get(b.title or b.place, {})
            if "lat" in entry and within(b.country, entry["lat"], entry["lng"]):
                b.lat, b.lng = entry["lat"], entry["lng"]
            b.name = dutch_name(b, known)
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
    for lang in ("nl", "ru"):
        missing = [b.name for b in found if b.lang == lang and b.lat is None]
        print(f"{lang}: {len(missing)} zonder positie: {', '.join(missing[:15])}", file=sys.stderr)


if __name__ == "__main__":
    main()

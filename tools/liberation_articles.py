"""Bevrijdingen from the articles of single places, for the languages without a list.

Per language a search (500 hits per request) finds the articles that mention a liberation; their
text comes 50 per request. In each article the sentence that names a liberation and a date of
1941–1945 gives the liberation date, the date nearest the verb counting; a sentence that names
an occupation and a date of 1939–1942 gives the occupation date. Only an article whose place lies
in the language's area is a place; one a list already covers (within 3 km and 3 days) is left out.

Everything fetched is cached, so a rerun asks only for what is new.
"""

import datetime as dt
import json
import math
import re
import time
from dataclasses import dataclass

from tools import liberations as lists
from tools.liberations import Bevrijding, plain, strip_refs

SEARCH_LIMIT = 500


@dataclass(frozen=True)
class ArticleRule:
    lang: str
    country: str          # the country the places are counted under (a key of lists.BOUNDS)
    kamp: str             # who liberated them: "sovjet" or "westers"
    source: str
    queries: tuple        # search strings; their hits together are the candidates
    liberated: re.Pattern  # a word of a liberation sentence
    occupied: re.Pattern | None
    months: dict
    area: tuple           # (south, north, west, east) where the places must lie
    # The first year a liberation is likely: in Ukraine none came before 1942 (the counterattacks
    # of 1941 did not reach it), so an earlier date is about something else.
    first_liberation: int = 1942
    # The years an Axis occupation could begin: before 1941 the dates in these articles are the
    # Soviet annexations (Western Ukraine 1939, Bessarabia 1940), not an occupation.
    occupation_years: tuple = (1941, 1942)
    verb: str = "bevrijd"  # "ingenomen" for a town in an Axis country
    # Wikidata classes of this language's villages and towns, on top of SETTLEMENTS.
    settlements: frozenset = frozenset()
    # A language whose dates are not "day month year" (Hungarian "1944. október 20.") gives its
    # own finder: (sentence, months) → [(position, ISO date)].
    dates: object = None
    # Per place, after its position is known: a function (Bevrijding) → Bevrijding or None (drop)
    # that may change verb, kamp, country or occupied by where the place lies (a German town in
    # today's Poland was taken, not liberated; west Bohemia was the US Army's).
    adjust: object = None
    # The month names as they stand without a day ("в марте 1943", "у березні 1944"): word →
    # month. With them an article that gives only a month and year still counts, apart, as a
    # Bevrijding known to the month (kept for later, not on the map).
    month_forms: object = None


def _rules():
    """Every rule in tools/liberation_rules: one module per language, each with RULE (or RULES)."""
    import importlib
    import pkgutil

    from tools import liberation_rules
    found = {}
    for module in pkgutil.iter_modules(liberation_rules.__path__):
        loaded = importlib.import_module(f"tools.liberation_rules.{module.name}")
        for rule in getattr(loaded, "RULES", None) or [loaded.RULE]:
            found[rule.source] = rule
    return dict(sorted(found.items()))




# The Wikidata classes of a settlement (P31), so a school, a factory, a camp or a raion (an area,
# not a place) with a liberation in its article does not count. Extended per language as its
# villages turn up under their own class.
SETTLEMENTS = {
    "Q486972",    # human settlement
    "Q532",       # village
    "Q3957",      # town
    "Q515",       # city
    "Q5084",      # hamlet
    "Q7930989",   # city or town
    "Q1549591",   # big city
    "Q1637706",   # million city
    "Q2264924",   # port city
    "Q2514025",   # posyolok
    "Q2989457",   # urban-type settlement
}


# --- Text ----------------------------------------------------------------------------------

def _dates(sentence, months):
    """Every day-month-year in a sentence: (position, ISO date)."""
    pattern = "|".join(months)
    found = []
    for match in re.finditer(rf"\b(\d{{1,2}})\s+({pattern})\b\s*(?:(\d{{4}}))?", sentence.lower()):
        year = match.group(3)
        if year is None:
            later = re.search(r"\b(19[34]\d)\b", sentence[match.end():match.end() + 40])
            year = later.group(1) if later else None
        if year is None:
            continue
        try:
            date = dt.date(int(year), months[match.group(2)], int(match.group(1)))
        except ValueError:
            continue
        found.append((match.start(), date.isoformat()))
    return found


# Date templates whose arguments are the date itself ({{date|4 octobre 1943}}, {{date-|10|août|1944}},
# {{data|25|aprile|1945}}): their words stay, named arguments go; "{{1er}} septembre" is the 1st.
DATE_TEMPLATE = re.compile(r"\{\{\s*(?:date-?|data|datum|дата)\s*\|([^{}]*)\}\}", re.IGNORECASE)
FIRST = re.compile(r"\{\{\s*1er\s*\}\}")


def _unwrap_dates(text):
    text = DATE_TEMPLATE.sub(lambda m: " ".join(p.strip() for p in m.group(1).split("|") if "=" not in p), text)
    return FIRST.sub("1", text)


# A full stop that ends no sentence: after a day or month ("8. 5. 1945") or a short
# abbreviation of year or "number" (Polish r., Russian г., Ukrainian р., Czech č.).
NO_END = re.compile(r"(?:\b\d{1,2}|\b(?:r|g|г|р|č|n|nr|ok|tzw|gen|płk))\.$", re.IGNORECASE)


def _split(text):
    """Sentences: a full stop and a space, unless the next word begins in lower case or the stop
    belongs to a number or an abbreviation."""
    found = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        if found and (part[:1].islower() or NO_END.search(found[-1])):
            found[-1] += " " + part
        else:
            found.append(part)
    return found


def sentences(wikitext):
    """The plain sentences of an article that mention a year of the war."""
    found = []
    # Line by line first: a table row (the fallen of a village) stays apart from the prose.
    for line in _unwrap_dates(strip_refs(wikitext)).replace("&nbsp;", " ").split("\n"):
        text = plain(line)
        found += [s for s in _split(text) if re.search(r"\b19(39|4[0-5])\b", s)]
    return found


def _nearest(sentence, verb, months, first_year, last_year, finder=None):
    """The date in `sentence` nearest a match of `verb`, within the years; None without both."""
    verbs = [m.start() for m in verb.finditer(sentence)]
    dates = [(at, iso) for at, iso in (finder or _dates)(sentence, months) if first_year <= int(iso[:4]) <= last_year]
    if not verbs or not dates:
        return None
    return min(dates, key=lambda d: min(abs(d[0] - v) for v in verbs))[1]


def read_article(rule, wikitext):
    """(occupied, liberated) of a place from its article; liberated None when it says none."""
    liberated = occupied = None
    for sentence in sentences(wikitext):
        # A row of a table (the fallen of the village) is no sentence about the place.
        if sentence.count("|") >= 3:
            continue
        if liberated is None:
            liberated = _nearest(sentence, rule.liberated, rule.months, rule.first_liberation, 1945, rule.dates)
        if occupied is None and rule.occupied is not None:
            occupied = _nearest(sentence, rule.occupied, rule.months, *rule.occupation_years, rule.dates)
    if liberated and occupied and occupied >= liberated:
        occupied = None
    return occupied, liberated


def _months(sentence, forms):
    """Every month-and-year without a day in a sentence: (position, "YYYY-MM")."""
    pattern = "|".join(sorted(forms, key=len, reverse=True))
    found = []
    for match in re.finditer(rf"\b({pattern})\b\D{{0,12}}?(19[34]\d)", sentence.lower()):
        found.append((match.start(), f"{match.group(2)}-{forms[match.group(1)]:02d}"))
    return found


def read_month(rule, wikitext):
    """The month (YYYY-MM) a place was liberated, from an article that gives no day: the month
    nearest a liberation word, 1943–1945. None without month forms or without such a month."""
    if not rule.month_forms:
        return None
    for sentence in sentences(wikitext):
        if sentence.count("|") >= 3:
            continue
        verbs = [m.start() for m in rule.liberated.finditer(sentence)]
        months = [(at, ym) for at, ym in _months(sentence, rule.month_forms) if 1943 <= int(ym[:4]) <= 1945]
        if verbs and months:
            return min(months, key=lambda m: min(abs(m[0] - v) for v in verbs))[1]
    return None


# --- Requests ------------------------------------------------------------------------------

def search(rule):
    """The titles the rule's queries find, 500 per request."""
    path = lists.CACHE / f"search-{rule.lang}.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    titles = set()
    for query in rule.queries:
        if query not in cached:
            hits, offset = [], 0
            while offset is not None and offset < 10000:
                data = json.loads(lists._get(f"https://{rule.lang}.wikipedia.org/w/api.php", {
                    "action": "query", "format": "json", "formatversion": "2", "list": "search",
                    "srsearch": query, "srlimit": str(SEARCH_LIMIT), "srnamespace": "0", "srprop": "",
                    "sroffset": str(offset),
                }))
                hits += [hit["title"] for hit in data.get("query", {}).get("search", [])]
                offset = data.get("continue", {}).get("sroffset")
                time.sleep(lists.PAUSE)
            cached[query] = hits
            lists.CACHE.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cached, ensure_ascii=False))
        titles.update(cached[query])
    return sorted(titles)


def texts(rule, titles):
    """{title: the article's lines that name a year of the war}, 50 articles per request, cached."""
    path = lists.CACHE / f"lines-{rule.lang}.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    wanted = [t for t in titles if t not in cached]
    for start in range(0, len(wanted), lists.BATCH):
        chunk = wanted[start:start + lists.BATCH]
        data = json.loads(lists._get(f"https://{rule.lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "formatversion": "2", "prop": "revisions",
            "rvprop": "content", "rvslots": "main", "titles": "|".join(chunk),
        }))
        query = data.get("query", {})
        alias = {e["from"]: e["to"] for e in query.get("normalized", [])}
        pages = {p["title"]: p for p in query.get("pages", [])}
        for title in chunk:
            page = pages.get(alias.get(title, title), {})
            revisions = page.get("revisions") or [{}]
            content = revisions[0].get("slots", {}).get("main", {}).get("content", "")
            # Only the lines that can hold a date of the war are kept, as wikitext: the cache stays
            # small, and a change in how sentences are read needs no new requests.
            cached[title] = "\n".join(line for line in strip_refs(content).split("\n")
                                      if re.search(r"19(39|4[0-5])", line))
        time.sleep(lists.PAUSE)
        lists.CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached, ensure_ascii=False))
    return cached


def classes(lang, titles):
    """{title: [Wikidata classes (P31)]}: the items from the Wikipedia API, their classes from
    Wikidata, 50 per request each; cached."""
    path = lists.CACHE / f"classes-{lang}.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    wanted = sorted(set(titles) - set(cached))
    items = {}
    for start in range(0, len(wanted), lists.BATCH):
        chunk = wanted[start:start + lists.BATCH]
        data = json.loads(lists._get(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "prop": "pageprops", "ppprop": "wikibase_item", "titles": "|".join(chunk),
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
            cached[title] = []
            item = pages.get(name, {}).get("pageprops", {}).get("wikibase_item")
            if item:
                items.setdefault(item, []).append(title)
        time.sleep(lists.PAUSE)
    ids = sorted(items)
    for start in range(0, len(ids), lists.BATCH):
        chunk = ids[start:start + lists.BATCH]
        data = json.loads(lists._get("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "format": "json", "props": "claims", "ids": "|".join(chunk),
        }))
        for item, entity in data.get("entities", {}).items():
            found = [claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                     for claim in entity.get("claims", {}).get("P31", [])]
            for title in items.get(item, []):
                cached[title] = [c for c in found if c]
        time.sleep(lists.PAUSE)
    if wanted:
        lists.CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cached, ensure_ascii=False))
    return cached


def _km(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _days(a, b):
    return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)


def already_listed(b, listed):
    """True when a list already has this place's liberation: within 3 km and 3 days."""
    return any(
        _days(b.liberated, other.liberated) <= 3 and _km((b.lat, b.lng), (other.lat, other.lng)) <= 3
        for other in listed if other.lat is not None
    )


def harvest(rule, listed, months=None):
    """The Bevrijdingen of the rule's language that the lists do not have yet. When `months` is a
    list, the places known only to the month are added to it (liberated "YYYY-MM", precision
    "month"), unless a place with a day already stands within 3 km."""
    titles = search(rule)
    found_texts = texts(rule, titles)
    read, by_month = {}, {}
    for title in titles:
        occupied, liberated = read_article(rule, found_texts.get(title, ""))
        if liberated:
            read[title] = (occupied, liberated)
        elif months is not None:
            month = read_month(rule, found_texts.get(title, ""))
            if month:
                by_month[title] = month
    kinds = classes(rule.lang, [*read, *by_month])
    accepted = SETTLEMENTS | rule.settlements
    read = {title: dates for title, dates in read.items() if accepted & set(kinds.get(title, []))}
    by_month = {title: month for title, month in by_month.items() if accepted & set(kinds.get(title, []))}
    known = lists.lookup(rule.lang, [*read, *by_month])
    south, north, west, east = rule.area

    def place(title, entry, **dates):
        b = Bevrijding(
            place=re.sub(r"\s*\(.*\)$", "", title), title=title, lang=rule.lang, country=rule.country,
            lat=entry["lat"], lng=entry["lng"], source=rule.source, **dates,
        )
        b.kamp = rule.kamp
        b.verb = rule.verb
        b.name = entry.get("nl") or entry.get("en") or lists.transliterate(b.place)
        return b

    def inside(entry):
        return "lat" in entry and south <= entry["lat"] <= north and west <= entry["lng"] <= east

    found = []
    for title, (occupied, liberated) in sorted(read.items()):
        entry = known.get(title, {})
        if not inside(entry):
            continue
        b = place(title, entry, liberated=liberated, occupied=occupied)
        if rule.adjust is not None:
            b = rule.adjust(b)
            if b is None:
                continue
        if not already_listed(b, listed):
            found.append(b)
    if months is not None:
        placed = [b for b in [*listed, *found, *months] if b.lat is not None]
        for title, month in sorted(by_month.items()):
            entry = known.get(title, {})
            if not inside(entry):
                continue
            b = place(title, entry, liberated=month, precision="month")
            if not any(_km((b.lat, b.lng), (other.lat, other.lng)) <= 3 for other in placed):
                months.append(b)
                placed.append(b)
    return found


def main(argv=None):
    """A trial run of one language without writing bevrijdingen.json: what its rule finds beyond
    what the file already has, with a sample to check by eye.

        poetry run python -m tools.liberation_articles SOURCE [--sample N] [--output FILE]
    """
    import argparse
    import random
    import sys
    from dataclasses import asdict, fields
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Trial run of one language's ArticleRule")
    parser.add_argument("source", help="the rule's source, e.g. uk-articles")
    parser.add_argument("--sample", type=int, default=25)
    parser.add_argument("--output", help="also write what it finds as JSON")
    args = parser.parse_args(argv)
    rule = _rules()[args.source]
    names = {f.name for f in fields(Bevrijding)}
    current = json.loads(Path("frontend/battles/bevrijdingen.json").read_text())
    listed = [Bevrijding(**{"title": None, **{k: v for k, v in r.items() if k in names}}) for r in current
              if r.get("lat") is not None and r["source"] != rule.source]
    found = harvest(rule, listed)
    print(f"{rule.source}: {len(found)} Bevrijdingen", file=sys.stderr)
    for b in random.Random(1).sample(found, min(args.sample, len(found))):
        print(f"  {b.title} | {b.name} | bezet {b.occupied} | {b.verb} {b.liberated} | {b.lat},{b.lng}", file=sys.stderr)
    if args.output:
        Path(args.output).write_text(json.dumps([asdict(b) for b in found], ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()

"""Extract the World War II battles from a dump of English Wikipedia.

The dump (enwiki-latest-pages-articles.xml.bz2, 25.8 GB compressed) is streamed once and
never held in memory. Every article with a military conflict infobox that overlaps the
war and names World War II becomes one record in frontend/battles/battles.json. Dates
and coordinates are parsed from wikitext and anything not understood is left out:

    poetry run python -m tools.extract_battles [dump.xml.bz2 | directory] [--output FILE]
"""
import argparse
import bz2
import calendar
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import quote

DEFAULT_DUMP = Path("~/.cache/uboats/wikipedia/")
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "frontend" / "battles" / "battles.json"
WAR_START = date(1939, 9, 1)
WAR_END = date(1945, 9, 2)
PROGRESS_EVERY = 100_000
READ_SIZE = 1 << 20
SAVE_EVERY_SECONDS = 60
CANDIDATE = re.compile(rb"infobox[ _]+(?:military[ _]+conflict|military[ _]+operation|battle)", re.IGNORECASE)
MAX_PLACE = 160
WIKI_URL = "https://en.wikipedia.org/wiki/"

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
MONTH_NAMES = [name.capitalize() for name in MONTHS]
MONTH_PATTERN = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?"
    r"|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?",
    re.IGNORECASE,
)

INFOBOX = re.compile(
    r"\{\{\s*infobox[\s_]+(?:military[\s_]+conflict|military[\s_]+operation|battle)\s*(?=[|\n}]|$)",
    re.IGNORECASE,
)
COMMENT = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)
# A self-closing note, a note with its end tag, or a note the excerpt or page cuts off.
REF = re.compile(r"<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref\s*>|<ref\b.*", re.DOTALL | re.IGNORECASE)
BREAK = re.compile(r"<br\b[^>]*>", re.IGNORECASE)
TAG = re.compile(r"<[^>]*>")
INNERMOST_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
WWII = re.compile(r"\b(?:World War II|Second World War|WWII)\b", re.IGNORECASE)
CATEGORY_LINE = re.compile(r"^\s*\[\[\s*category\s*:[^\n]*", re.IGNORECASE | re.MULTILINE)
COORD = re.compile(r"\{\{\s*coord(?:inates)?\s*\|", re.IGNORECASE)
KEEP_ARGUMENT = {"nowrap", "nobr", "circa", "c.", "ca.", "c"}
SPACING = {"snd": " – ", "spaced ndash": " – ", "ndash": "–", "en dash": "–", "nbsp": " "}
DATE_TEMPLATES = {"start date", "start date and age", "end date", "end date and age"}
PARENTHESES = re.compile(r"\([^()]*\)")
CIRCA = re.compile(r"\b(?:circa|ca\.|c\.)\s*", re.IGNORECASE)
RANGE_SEPARATOR = re.compile(r"\s*[–—-]\s*|\s+to\s+", re.IGNORECASE)


class DateSkip(Exception):
    """The date cannot be used; reason is what the skip report counts it under."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class ParsedDate:
    def __init__(self, start, end, precision, text):
        self.start = start
        self.end = end
        self.precision = precision
        self.text = text


def strip_comments(text):
    return COMMENT.sub("", text)


def find_infobox(text):
    """Fields (lower-case name to raw value) of the first conflict infobox, or None."""
    text = strip_comments(text)
    match = INFOBOX.search(text)
    if match is None:
        return None
    fields = {}
    depth = 0
    start = match.end()
    pieces = []
    i = start
    while i < len(text):
        pair = text[i : i + 2]
        if pair in ("{{", "[["):
            depth += 1
            i += 2
        elif pair in ("}}", "]]"):
            if depth == 0:
                break
            depth -= 1
            i += 2
        elif text[i] == "|" and depth == 0:
            pieces.append(text[start:i])
            start = i + 1
            i += 1
        else:
            i += 1
    pieces.append(text[start:i])
    for piece in pieces:
        name, equals, value = piece.partition("=")
        if equals and name.strip():
            fields[name.strip().lower()] = value.strip()
    return fields


def render_date(numbers):
    """Year, month and day from a date template as text; a lone year stays a bare year."""
    if len(numbers) == 3 and 1 <= int(numbers[1]) <= 12:
        return f"{int(numbers[2])} {MONTH_NAMES[int(numbers[1]) - 1]} {int(numbers[0])}"
    if len(numbers) == 2 and 1 <= int(numbers[1]) <= 12:
        return f"{MONTH_NAMES[int(numbers[1]) - 1]} {int(numbers[0])}"
    return numbers[0] if len(numbers) == 1 else ""


def expand_template(body, dates):
    parts = [part.strip() for part in body.split("|")]
    name = re.sub(r"[\s_]+", " ", parts[0].lower())
    arguments = [part for part in parts[1:] if "=" not in part]
    if name in SPACING:
        return SPACING[name]
    if name in KEEP_ARGUMENT:
        return arguments[0] if arguments else ""
    if not dates:
        return ""
    numbers = [a for a in arguments if a.isdigit()]
    if name in DATE_TEMPLATES:
        return render_date(numbers[:3])
    if name == "start and end dates" and len(numbers) >= 6:
        return f"{render_date(numbers[:3])} – {render_date(numbers[3:6])}"
    return ""


def remove_templates(text, dates=False):
    previous = None
    while previous != text:
        previous = text
        text = INNERMOST_TEMPLATE.sub(lambda m: expand_template(m.group(1), dates), text)
    return re.sub(r"\{\{.*", "", text, flags=re.DOTALL)


def tidy(text):
    text = LINK.sub(r"\1", text)
    text = re.sub(r"\[\[|\]\]", "", text)
    text = html.unescape(TAG.sub("", text)).replace("\xa0", " ")
    text = text.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_date_text(raw):
    text = REF.sub("", strip_comments(raw))
    text = BREAK.split(text, 1)[0]
    return tidy(PARENTHESES.sub("", remove_templates(text, dates=True)))


def plain_text(raw):
    text = REF.sub("", strip_comments(raw))
    text = BREAK.sub(", ", text)
    text = tidy(remove_templates(text))
    text = re.sub(r"(?:\s*,)+", ",", text)
    return re.sub(r"\s+,", ",", text).strip(" ,")


def parse_part(part):
    """(day, month, year) found in one side of a date range; each may be None."""
    text = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", part)
    text = CIRCA.sub("", text)
    months = MONTH_PATTERN.findall(text)
    text = MONTH_PATTERN.sub(" ", text)
    years = re.findall(r"\b\d{4}\b", text)
    text = re.sub(r"\b\d{4}\b", " ", text)
    days = re.findall(r"\b\d{1,2}\b", text)
    text = re.sub(r"\b\d{1,2}\b", " ", text)
    text = re.sub(r"\bof\b", " ", text, flags=re.IGNORECASE)
    if len(months) > 1 or len(years) > 1 or len(days) > 1 or re.search(r"[^\s.,]", text):
        raise DateSkip("not understood")
    month = None
    if months:
        month = next(i for i, name in enumerate(MONTHS, 1) if name.startswith(months[0].lower()[:3]))
    return (int(days[0]) if days else None, month, int(years[0]) if years else None)


def parse_date(raw):
    """Start, end and precision from the `date` field of an infobox, or DateSkip."""
    text = clean_date_text(raw)
    if not text:
        raise DateSkip("no date")
    normalized = re.sub(
        r"\b(\d{4})-(\d{2})-(\d{2})\b",
        lambda m: f"{int(m.group(3))} {MONTH_NAMES[int(m.group(2)) - 1] if 1 <= int(m.group(2)) <= 12 else '?'} {m.group(1)}",
        text,
    )
    parts = RANGE_SEPARATOR.split(normalized)
    if len(parts) > 2 or any(not p.strip() for p in parts):
        raise DateSkip("not understood")
    first, last = (parse_part(p) for p in parts) if len(parts) == 2 else (parse_part(parts[0]),) * 2
    single = len(parts) == 1

    (d1, m1, y1), (d2, m2, y2) = first, last
    if not single:
        if m2 is None and d2 is not None:
            m2 = m1
        if m1 is None and d1 is not None:
            m1 = m2
    if m1 is None or m2 is None:
        if m1 is None and m2 is None and (y1 is not None or y2 is not None) and d1 is None and d2 is None:
            raise DateSkip("only a year")
        raise DateSkip("not understood")
    year_inferred = False
    if single:
        y2 = y1
    if y2 is None:
        y2 = y1
    if y1 is None:
        y1, year_inferred = y2, True
    if y1 is None:
        raise DateSkip("not understood")
    try:
        end_day = d2 if d2 is not None else calendar.monthrange(y2, m2)[1]
        start = date(y1, m1, d1 if d1 is not None else 1)
        end = date(y2, m2, end_day)
        if start > end and year_inferred and m1 > m2:
            start = date(y1 - 1, m1, d1 if d1 is not None else 1)
    except (ValueError, calendar.IllegalMonthError):
        raise DateSkip("not understood")
    if start > end:
        raise DateSkip("not understood")
    precision = "day" if d1 is not None and d2 is not None else "month"
    return ParsedDate(start, end, precision, text)


def extract_coordinates(text):
    """Latitude and longitude of the first {{coord}} in the text, or (None, None)."""
    match = COORD.search(strip_comments(text))
    if match is None:
        return None, None
    body = strip_comments(text)[match.end():]
    depth = 0
    end = len(body)
    for i in range(len(body)):
        pair = body[i : i + 2]
        if pair == "{{":
            depth += 1
        elif pair == "}}":
            if depth == 0:
                end = i
                break
            depth -= 1
    tokens = [t.strip() for t in re.split(r"\|", body[:end]) if "=" not in t and ":" not in t and t.strip()]
    try:
        position = coordinate_position(tokens)
    except ValueError:
        return None, None
    return position if position is not None else (None, None)


def coordinate_position(tokens):
    letters = [t.upper() for t in tokens if t.upper() in ("N", "S", "E", "W")]
    if not letters:
        if len(tokens) != 2:
            return None
        lat, lng = float(tokens[0]), float(tokens[1])
        return checked(lat, lng)
    groups = []
    current = []
    for token in tokens:
        if token.upper() in ("N", "S", "E", "W"):
            groups.append((token.upper(), current))
            current = []
        else:
            current.append(float(token))
    if len(groups) < 2 or groups[0][0] not in "NS" or groups[1][0] not in "EW":
        return None
    values = []
    for hemisphere, numbers in groups[:2]:
        if not 1 <= len(numbers) <= 3 or any(n < 0 for n in numbers):
            return None
        if any(n >= 60 for n in numbers[1:]):
            return None
        degrees = sum(n / 60**i for i, n in enumerate(numbers))
        values.append(-degrees if hemisphere in "SW" else degrees)
    return checked(values[0], values[1])


def checked(lat, lng):
    if abs(lat) > 90 or abs(lng) > 180:
        return None
    return round(lat, 5), round(lng, 5)


def names_world_war_ii(text, fields):
    for name in ("part_of", "partof", "campaign"):
        if WWII.search(fields.get(name, "")):
            return True
    return any(WWII.search(line) for line in CATEGORY_LINE.findall(text))


def short_place(place):
    if len(place) <= MAX_PLACE:
        return place
    cut = place[:MAX_PLACE].rpartition(",")[0] or place[:MAX_PLACE]
    return cut.rstrip(" ,") + "…"


def wiki_url(title):
    return WIKI_URL + quote(title.replace(" ", "_"), safe="_(),:'!*;@$&=+~-./")


def extract_battle(title, text):
    """(record, None) for a World War II battle, otherwise (None, reason)."""
    fields = find_infobox(text)
    if fields is None:
        return None, "no infobox"
    try:
        parsed = parse_date(fields.get("date", ""))
    except DateSkip as skip:
        return None, f"date: {skip.reason}"
    if parsed.end < WAR_START or parsed.start > WAR_END:
        return None, "outside the war period"
    text = strip_comments(text)
    if not names_world_war_ii(text, fields):
        return None, "does not name World War II"
    lat, lng = extract_coordinates(text)
    part_of = next((plain_text(fields[n]) for n in ("part_of", "partof", "campaign") if fields.get(n)), None)
    place = next((plain_text(fields[n]) for n in ("place", "location") if fields.get(n)), None)
    return {
        "title": title,
        "url": wiki_url(title),
        "start": parsed.start.isoformat(),
        "end": parsed.end.isoformat(),
        "precision": parsed.precision,
        "date_text": parsed.text,
        "lat": lat,
        "lng": lng,
        "part_of": part_of or None,
        "place": short_place(place) if place else None,
    }, None


def iter_raw_pages(path):
    """The bytes of each page in the dump, in order, ending just before its closing tag."""
    with bz2.open(path, "rb") as stream:
        pending = b""
        while chunk := stream.read(READ_SIZE):
            parts = (pending + chunk).split(b"</page>")
            pending = parts.pop()
            yield from parts


def iter_candidate_pages(path, skip_pages=0):
    """(page number, title, wikitext) of articles with a conflict infobox, streamed from the dump.

    Nearly every page in the dump has no such infobox, so a byte search rules those out
    before any XML is parsed. Page numbers count every page, so that a run can resume.
    """
    for number, raw in enumerate(iter_raw_pages(path), 1):
        if number <= skip_pages or CANDIDATE.search(raw) is None:
            continue
        start = raw.rfind(b"<page>")
        page = ET.fromstring(raw[start:] + b"</page>")
        if page.findtext("ns") == "0" and page.find("redirect") is None and page.findtext("title"):
            yield number, page.findtext("title"), page.findtext("revision/text") or ""


def resolve_dump(path):
    path = Path(path).expanduser()
    if not path.is_dir():
        return path
    candidates = sorted(c for c in path.glob("*pages-articles*.xml*.bz2") if "multistream" not in c.name)
    if not candidates:
        raise SystemExit(f"No pages-articles dump (*.xml.bz2) found in {path}")
    return candidates[-1]


def _write_atomically(path, text):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def run(dump, output, save_every_seconds=SAVE_EVERY_SECONDS):
    """Add the dump's battles to `output`, saving along the way so that a page can show them
    during the run and a stopped run can continue where it was."""
    dump = resolve_dump(dump)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    progress_path = dump.with_name(f"{output.stem}.progress.json")
    progress = _load_json(progress_path, {"pages": 0, "skipped": {}, "review": []})
    skipped = Counter(progress["skipped"])
    review = progress["review"]
    review_path = dump.with_name(f"{output.stem}.skipped.txt")
    battles = {battle["title"]: battle for battle in _load_json(output, [])}
    pages = progress["pages"]

    def save():
        ordered = sorted(battles.values(), key=lambda b: (b["start"], b["title"]))
        _write_atomically(output, json.dumps(ordered, ensure_ascii=False, separators=(",", ":")))
        _write_atomically(review_path, "".join(f"{line}\n" for line in review))
        _write_atomically(progress_path, json.dumps({"pages": pages, "skipped": skipped, "review": review}))

    last_save = time.monotonic()
    last_report = pages
    for pages, title, text in iter_candidate_pages(dump, skip_pages=pages):
        battle, reason = extract_battle(title, text)
        if battle is None:
            skipped[reason] += 1
            fields = find_infobox(text)
            if reason.startswith("date") and fields and names_world_war_ii(strip_comments(text), fields):
                review.append(f"{title}\t{reason}\t{fields.get('date', '')[:200]}".replace("\n", " "))
        else:
            battles[title] = battle
        if time.monotonic() - last_save >= save_every_seconds:
            save()
            last_save = time.monotonic()
        if pages - last_report >= PROGRESS_EVERY:
            last_report = pages
            print(f"{pages} pages read, {len(battles)} battles so far", file=sys.stderr, flush=True)
    save()
    progress_path.unlink()
    print(f"{len(battles)} battles written to {output}")
    for reason, count in skipped.most_common():
        print(f"  {reason}: {count}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dump", nargs="?", default=DEFAULT_DUMP, help="the .xml.bz2 dump, or the directory holding it")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="where to write battles.json")
    arguments = parser.parse_args(argv)
    run(arguments.dump, arguments.output)


if __name__ == "__main__":
    main()

"""Veldslagen from Wikipedias in other languages than English.

Everything that differs per language lives in one Language entry: the infobox, its field
names, the month names and how coordinates are written. Adding a language means adding an
entry here (and its words in tools.battle_winner).
"""

import re
from dataclasses import dataclass, field
from urllib.parse import quote

from tools.extract_battles import (
    WAR_END,
    WAR_START,
    DateSkip,
    checked,
    clean_date_text,
    coordinate_position,
    extract_coordinates,
    find_infobox,
    parse_date,
    plain_text,
    short_place,
    strip_comments,
)


@dataclass(frozen=True)
class Language:
    code: str
    infobox: re.Pattern
    candidate: re.Pattern  # a byte search that rules out most pages before any parsing
    date: str
    place: str
    part_of: str
    result: str
    side1: str
    side2: str
    months: dict = field(default_factory=dict)
    date_end: str | None = None
    range_words: tuple = ()
    coord_field: str | None = None


def _infobox(*names):
    alternatives = "|".join(re.escape(n).replace(r"\ ", r"[\s_]+") for n in names)
    return re.compile(r"\{\{\s*(?:" + alternatives + r")\s*(?=[|\n}]|$)", re.IGNORECASE)


def _candidate(*names):
    alternatives = b"|".join(re.escape(n.encode("utf-8")).replace(rb"\ ", rb"[ _]+") for n in names)
    return re.compile(alternatives, re.IGNORECASE)


def _months(*rows):
    """English month name for each local spelling; rows are given January to December."""
    english = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
    table = {}
    for row in rows:
        for name, month in zip(row, english):
            if name:
                table[name.lower()] = month
    return table


NL_INFOBOX = ("Infobox militair conflict", "Infobox veldslag")
DE_INFOBOX = ("Infobox Militärischer Konflikt",)
PL_INFOBOX = ("Wojna infobox", "Bitwa infobox", "Konflikt zbrojny infobox")

LANGUAGES = {
    "nl": Language(
        code="nl",
        infobox=_infobox(*NL_INFOBOX),
        candidate=_candidate(*NL_INFOBOX),
        date="date", place="place", part_of="partof", result="result", side1="combatant1", side2="combatant2",
        months=_months(("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                        "september", "oktober", "november", "december")),
        range_words=("tot",),
    ),
    "de": Language(
        code="de",
        infobox=_infobox(*DE_INFOBOX),
        candidate=_candidate(*DE_INFOBOX),
        date="datum", date_end="datumbis", place="ort", part_of="teilvon", result="ausgang",
        side1="kontrahent1", side2="kontrahent2",
        months=_months(("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                        "September", "Oktober", "November", "Dezember"),
                       ("Jänner",) + ("",) * 11),
        range_words=("bis",),
    ),
    "pl": Language(
        code="pl",
        infobox=_infobox(*PL_INFOBOX),
        candidate=_candidate(*PL_INFOBOX),
        date="czas", place="miejsce", part_of="konflikt", result="wynik", side1="strona1", side2="strona2",
        months=_months(("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
                        "września", "października", "listopada", "grudnia"),
                       ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień",
                        "wrzesień", "październik", "listopad", "grudzień")),
        range_words=("do",),
        coord_field="współrzędne",
    ),
}

# The order in which other languages are asked for a title, a position or a Winnaar.
ORDER = ("nl", "de", "pl")


def wiki_url(lang, title):
    return f"https://{lang}.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="_(),:'!*;@$&=+~-./")


def english_date(lang, text):
    """A cleaned date text with local month names and range words in English, so the English
    date parser can read it. German day numbers lose their dot: `5. Juli` becomes `5 July`."""
    language = LANGUAGES[lang]
    names = sorted(language.months, key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(n) for n in names) + r")(?!\w)", re.IGNORECASE)
    text = pattern.sub(lambda m: language.months[m.group(1).lower()], text)
    text = re.sub(r"\b(\d{1,2})\.(?=\s|$|[–—-])", r"\1", text)
    for word in language.range_words:
        text = re.sub(rf"\s+{word}\s+", " – ", text)
    return re.sub(r"\s+", " ", text).strip()


_COOR_NL = re.compile(r"\{\{\s*Coor[\s_]+(?:title[\s_]+)?(?:dms|dm|d|dec)\s*\|([^{}]*)\}\}", re.IGNORECASE)
_COORDINATE_DE = re.compile(r"\{\{\s*Coordinate\s*\|([^{}]*)\}\}", re.IGNORECASE)


def _tokens(body):
    return [t.strip() for t in body.split("|") if t.strip() and "=" not in t and ":" not in t]


def _position(tokens):
    try:
        return coordinate_position(tokens)
    except ValueError:
        return None


def _german(body):
    named = dict(part.split("=", 1) for part in body.split("|") if "=" in part)
    ns, ew = named.get("NS", "").strip(), named.get("EW", "").strip()
    if not ns or not ew:
        return None
    if "/" in ns or "/" in ew:
        return _position([t for t in ns.split("/") + ew.split("/") if t.strip()])
    try:
        return checked(float(ns), float(ew))
    except ValueError:
        return None


def other_coordinates(lang, text):
    """Latitude and longitude written the way this language does, else a {{coord}}, else (None, None)."""
    text = strip_comments(text)
    position = None
    if lang == "nl":
        match = _COOR_NL.search(text)
        position = match and _position(_tokens(match.group(1)))
    elif lang == "de":
        match = _COORDINATE_DE.search(text)
        position = match and _german(match.group(1))
    elif lang == "pl":
        fields = find_infobox(text, LANGUAGES["pl"].infobox) or {}
        raw = fields.get(LANGUAGES["pl"].coord_field, "")
        tokens = re.findall(r"\d+(?:[.,]\d+)?|[NSEW]\b", raw)
        position = tokens and _position([t.replace(",", ".") for t in tokens])
    if not position:
        position = _degree_fields(text)
    if position:
        return position
    return extract_coordinates(text)


_DEGREE_FIELD = re.compile(r"\|\s*(lat|lon|long)_(deg|min|sec|dir)\s*=\s*([^|}\n]*)", re.IGNORECASE)


def _degree_fields(text):
    """A position from lat_deg/lat_min/lat_sec/lat_dir and lon_… fields (a location map in an infobox)."""
    values = {}
    for axis, part, value in _DEGREE_FIELD.findall(text):
        values.setdefault(("lat" if axis.lower() == "lat" else "lon", part.lower()), value.strip())
    if not values.get(("lat", "deg")) or not values.get(("lon", "deg")):
        return None
    tokens = []
    for axis, positive, negative in (("lat", "N", "S"), ("lon", "E", "W")):
        tokens += [values.get((axis, part)) or "0" for part in ("deg", "min", "sec")]
        direction = (values.get((axis, "dir")) or positive).upper()[:1]
        tokens.append(direction if direction in (positive, negative) else positive)
    return _position(tokens)


def extract_other_battle(lang, title, text):
    """(record, None) for a battle during the war in this language's Wikipedia, otherwise (None, reason)."""
    from tools import battle_winner

    language = LANGUAGES[lang]
    fields = find_infobox(text, language.infobox)
    if fields is None:
        return None, "no infobox"
    raw = fields.get(language.date, "")
    if language.date_end and fields.get(language.date_end, "").strip():
        raw = f"{raw} – {fields[language.date_end]}"
    try:
        parsed = parse_date(english_date(lang, clean_date_text(raw)))
    except DateSkip as skip:
        return None, f"date: {skip.reason}"
    if parsed.end < WAR_START or parsed.start > WAR_END:
        return None, "outside the war period"
    lat, lng = other_coordinates(lang, text)
    part_of = plain_text(fields.get(language.part_of, "")) or None
    place = plain_text(fields.get(language.place, "")) or None
    return {
        "title": title,
        "url": wiki_url(lang, title),
        "start": parsed.start.isoformat(),
        "end": parsed.end.isoformat(),
        "precision": parsed.precision,
        "date_text": parsed.text,
        "lat": lat,
        "lng": lng,
        "part_of": part_of,
        "place": short_place(place) if place else None,
        "winner": battle_winner.other_winner(lang, fields),
        "lang": lang,
    }, None

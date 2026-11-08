"""Translating the HTML of a rendered Artikel, keeping its structure.

The text between block elements (paragraphs, headings, list items, table cells, captions) is
translated as one piece per line, so that the model sees whole sentences. Links, bold and
italic inside it are put back where their text, or its translation, returns in the
translation; when it does not return, the element is left out and its text stays translated.
Lines that are only links (lists of commanders, places) and the Dutch labels of the infobox
are left as they are.
"""

import re
from collections.abc import Callable, Sequence
from html import escape
from html.parser import HTMLParser

from app.services.wiki.infobox import ROWS

INLINE = {"a", "b", "i", "em", "strong", "span", "sup", "sub"}
VOID = {"br", "img"}
LABELS = {label for label, _ in ROWS}
# The field names other Wikipedias' infoboxes show as labels, as Dutch labels: a word without
# context is translated badly (Дата became "Afspraakje"). A number after it is the side.
FIELD_LABELS = {
    "Strijdende partij": ("kontrahent", "combattants", "schieramento", "combatant", "strona", "противник"),
    "Bevelhebber": ("befehlshaber", "commandant", "comandante", "commander", "dowódca", "командир"),
    "Sterkte": ("truppenstärke", "forces", "effettivi", "strength", "siły", "силы"),
    "Verliezen": ("verluste", "pertes", "perdite", "casualties", "straty", "потери"),
    "Burgerslachtoffers": ("zivilverluste",),
    "Totale verliezen": ("общие потери",),
    "Datum": ("datum", "date", "data", "czas", "дата"),
    "Tot": ("datumbis",),
    "Plaats": ("ort", "lieu", "luogo", "place", "miejsce", "место"),
    "Resultaat": ("ausgang", "issue", "esito", "result", "wynik", "итог"),
    "Gevolgen": ("folgen",),
    "Onderdeel van": ("teilvon", "teil von", "guerre", "parte di", "partof", "campaign", "konflikt", "часть",
                      "conflit", "conflitto"),
    "Conflict": ("conflict", "конфликт", "nome del conflitto", "battle name", "nazwa"),
    "Aanleiding": ("casus", "przyczyna", "причина"),
    "Gebied": ("gebiete", "territoires", "mutamenti territoriali", "territory", "terytorium", "изменения"),
    "Eenheden": ("unités", "units"),
    "Veldslagen": ("batailles",),
    "Tijdperk": ("epoka",),
    "Type": ("tipo",),
    "Overzicht": ("überblick",),
    "Opmerkingen": ("notizen", "notes", "note"),
}
_FIELD_LABEL = {name: label for label, names in FIELD_LABELS.items() for name in names}
_FIELD = re.compile(r"^(.*?)\s*(\d*)$")


def field_label(text: str) -> str | None:
    """The Dutch label of another language's infobox field name ("Командир1" → "Bevelhebber 1")."""
    match = _FIELD.match(text.strip().lower().replace("_", " "))
    label = _FIELD_LABEL.get(match.group(1)) if match else None
    if label is None:
        return None
    return f"{label} {match.group(2)}" if match.group(2) else label
LETTER = re.compile(r"[^\W\d_]")
SPACE = re.compile(r"\s+")

Translate = Callable[[Sequence[str]], list[str]]


class _Element:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []

    def text(self):
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def html(self):
        attrs = "".join(f' {name}="{escape(value or "", quote=True)}"' for name, value in self.attrs)
        if self.tag in VOID:
            return f"<{self.tag}{attrs}>"
        return f"<{self.tag}{attrs}>{_html(self.children)}</{self.tag}>"


def _html(nodes):
    return "".join(escape(n, quote=False) if isinstance(n, str) else n.html() for n in nodes)


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Element("", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = _Element(tag, attrs)
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Element(tag, attrs))

    def handle_endtag(self, tag):
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _is_inline(node):
    return isinstance(node, str) or node.tag in INLINE


def _runs(element, found):
    """Collects (element, start, end) of each line of inline nodes, block elements recursively."""
    start = None
    children = element.children
    for index, child in enumerate(children + [None]):
        if child is not None and _is_inline(child):
            if start is None:
                start = index
            continue
        if start is not None:
            found.append((element, start, index))
            start = None
        if child is not None and child.tag not in VOID:
            _runs(child, found)


def _needs_translation(nodes):
    text = SPACE.sub(" ", _html_text(nodes)).strip()
    if not text or text in LABELS:
        return False
    return bool(LETTER.search(_loose_text(nodes)))


def _loose_text(nodes):
    """The text outside links, also inside bold or italic."""
    return "".join(n if isinstance(n, str) else "" if n.tag == "a" else _loose_text(n.children) for n in nodes)


def _html_text(nodes):
    return "".join(n if isinstance(n, str) else n.text() for n in nodes)


def _clone(element, text):
    copy = _Element(element.tag, element.attrs)
    copy.children = [text]
    return copy


def _relink(translated, elements, names):
    """The translated line as nodes, each element put back on its text or its translation."""
    claimed = []
    for element in elements:
        own = SPACE.sub(" ", element.text()).strip()
        for candidate, keep in ((own, True), (names.get(own, ""), False)):
            if len(candidate) < 2:
                continue
            pattern = (r"\b" if candidate[0].isalnum() else "") + re.escape(candidate) + (
                r"\b" if candidate[-1].isalnum() else "")
            for match in re.finditer(pattern, translated, flags=0 if keep else re.IGNORECASE):
                span = match.span()
                if all(span[1] <= a or span[0] >= b for a, b, _ in claimed):
                    claimed.append((span[0], span[1], element if keep else _clone(element, match.group())))
                    break
            else:
                continue
            break
    nodes, cursor = [], 0
    for start, end, element in sorted(claimed, key=lambda c: c[0]):
        if start > cursor:
            nodes.append(translated[cursor:start])
        nodes.append(element)
        cursor = end
    if cursor < len(translated):
        nodes.append(translated[cursor:])
    return nodes


def translate_html(html: str, translate: Translate) -> str:
    """The HTML with its text translated by `translate` (a list of texts in, their translations
    out), asked once for every line and every name of a link or emphasis in it."""
    parser = _Parser()
    parser.feed(html)
    parser.close()
    runs = []
    _runs(parser.root, runs)
    lines = []  # (element, start, end, [line nodes, separated by <br>])
    for element, start, end in runs:
        line, parts = [], []
        for node in element.children[start:end]:
            if not isinstance(node, str) and node.tag == "br":
                parts.append(line)
                line = []
            else:
                line.append(node)
        parts.append(line)
        lines.append((element, start, end, parts))
    wanted = []
    for element, _, _, parts in lines:
        for part in parts:
            if element.tag == "th" and field_label(_html_text(part)):
                continue
            if _needs_translation(part):
                wanted.append(SPACE.sub(" ", _html_text(part)).strip())
                wanted += [SPACE.sub(" ", n.text()).strip() for n in part if not isinstance(n, str)]
    unique = list(dict.fromkeys(t for t in wanted if t))
    translated = dict(zip(unique, translate(unique))) if unique else {}
    # Replace from the last line back, so the indexes of earlier lines stay right.
    for element, start, end, parts in reversed(lines):
        new = []
        for number, part in enumerate(parts):
            if number:
                new.append(_Element("br", []))
            if element.tag == "th" and (label := field_label(_html_text(part))):
                new.append(label)
                continue
            if not _needs_translation(part):
                new += part
                continue
            text = _html_text(part)
            lead = text[: len(text) - len(text.lstrip())]
            tail = text[len(text.rstrip()):]
            line = translated[SPACE.sub(" ", text).strip()]
            elements = [n for n in part if not isinstance(n, str)]
            new += ([lead] if lead else []) + _relink(line, elements, translated) + ([tail] if tail else [])
        element.children[start:end] = new
    return _html(parser.root.children)

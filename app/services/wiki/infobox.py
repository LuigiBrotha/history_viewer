"""The Artikel's own infobox, built from the fields of the dump's conflict infobox."""

import re
from collections.abc import Callable, Mapping

TAG = re.compile(r"<[^>]*>")
FILE_PREFIX = re.compile(r"^\s*(?:file|image)\s*:", re.IGNORECASE)
COMMENT = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)
MULTIPLE_IMAGE = re.compile(r"^\{\{\s*multiple[\s_]+image\b", re.IGNORECASE)
FIRST_OF_MULTIPLE = re.compile(r"\|\s*image1\s*=\s*([^|}]*)", re.IGNORECASE)

# (label, field names); one field is a single row, two are side 1 and side 2 next to each other.
ROWS = [
    ("Datum", ("date",)),
    ("Plaats", ("place",)),
    ("Resultaat", ("result",)),
    ("Gebied", ("territory",)),
    ("Strijdende partijen", ("combatant1", "combatant2")),
    ("Bevelhebbers", ("commander1", "commander2")),
    ("Sterkte", ("strength1", "strength2")),
    ("Verliezen", ("casualties1", "casualties2")),
]


def _is_empty(html: str) -> bool:
    return "<img" not in html and not TAG.sub("", html).strip()


def _image_wikitext(fields: Mapping[str, str]) -> str:
    """The infobox image as a file link, so it renders like any other figure."""
    image = COMMENT.sub("", fields.get("image", "")).strip()
    if MULTIPLE_IMAGE.match(image):
        first = FIRST_OF_MULTIPLE.search(image)
        image = first.group(1).strip() if first else ""
    if not image:
        return ""
    if image.startswith("[["):
        return image
    parts = [f"File:{FILE_PREFIX.sub('', image)}", "thumb"]
    if fields.get("alt", "").strip():
        parts.append(f"alt={fields['alt'].strip()}")
    parts.append(fields.get("caption", "").strip())
    return f"[[{'|'.join(parts)}]]"


def render_infobox(fields: Mapping[str, str], render_inline: Callable[[str], str]) -> str:
    """A table with the image, then one row per non-empty field in the fixed order."""
    fields = {**fields}
    if not fields.get("place", "").strip():
        fields["place"] = fields.get("location", "")
    rows = []
    image = _image_wikitext(fields)
    if image:
        figure = render_inline(image)
        if not _is_empty(figure):
            rows.append(f'<tr><td colspan="2">{figure}</td></tr>')
    for label, names in ROWS:
        cells = [render_inline(fields.get(name, "")).strip() for name in names]
        if all(_is_empty(cell) for cell in cells):
            continue
        if len(cells) == 1:
            rows.append(f"<tr><th>{label}</th><td>{cells[0]}</td></tr>")
        else:
            rows.append(f'<tr><th colspan="2">{label}</th></tr><tr><td>{cells[0]}</td><td>{cells[1]}</td></tr>')
    return f'<table class="article-infobox">{"".join(rows)}</table>'

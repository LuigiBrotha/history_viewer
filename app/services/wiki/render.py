"""A Veldslag's Artikel as HTML, rendered from the dump's raw wikitext without template expansion."""

import html
import logging
import re
from collections.abc import Callable, Iterable, Mapping
from urllib.parse import quote

import mwparserfromhell
from mwparserfromhell.nodes import ExternalLink, Heading, HTMLEntity, Tag, Template, Text, Wikilink

from app.services.wiki.dates import render_date
from app.services.wiki.infobox import render_infobox, render_plain_infobox
from app.services.wiki.sanitize import sanitize
from app.services.wiki.titles import normalize_title, wiki_url

LOG = logging.getLogger(__name__)

IMAGE_WIDTH = 330
INFOBOXES = {"infobox military conflict", "infobox military operation", "infobox battle"}
# The conflict infoboxes of the other languages; they are shown as a plain table of their fields.
FOREIGN_INFOBOXES = {
    "infobox militair conflict", "infobox veldslag", "infobox militärischer konflikt", "wojna infobox",
    "bitwa infobox", "konflikt zbrojny infobox", "вооружённый конфликт", "infobox conflit militaire", "conflitto",
    "battlebox", "infobox 軍事衝突",
}
FILE_NAMESPACES = {"file", "image", "bestand", "afbeelding", "datei", "bild", "plik", "grafika", "файл", "изображение",
                   "fichier", "immagine", "ファイル", "画像"}
CATEGORY_NAMESPACES = {"category", "categorie", "kategorie", "kategoria", "категория", "catégorie", "categoria", "カテゴリ"}
DROPPED_SECTIONS = {
    "references", "notes", "citations", "bibliography", "sources", "further reading", "external links", "see also",
    "footnotes",
    "bronnen", "noten", "referenties", "literatuur", "externe links", "zie ook", "voetnoten", "bronvermelding",
    "einzelnachweise", "literatur", "weblinks", "anmerkungen", "siehe auch", "quellen",
    "przypisy", "bibliografia", "linki zewnętrzne", "zobacz też", "uwagi",
    "примечания", "литература", "ссылки", "см. также", "комментарии", "источники",
    "notes et références", "notes", "références", "bibliographie", "liens externes", "voir aussi", "articles connexes",
    "note", "bibliografia", "collegamenti esterni", "voci correlate", "altri progetti",
    "脚注", "注釈", "出典", "参考文献", "関連項目", "外部リンク",
}
DATE_TEMPLATES = {"start date", "end date", "start date and age", "end date and age"}
FIRST_ARGUMENT = {"nowrap", "small", "flag", "flagcountry", "navy", "army", "air force", "center"}
SECOND_ARGUMENT = {"lang", "langx"}
CONVERT = {"convert", "cvt"}
LIST_TEMPLATES = {
    "ubl", "unbulleted list", "plainlist", "plain list", "indented plainlist", "flatlist", "collapsible list",
    "tree list", "bulleted list",
}
SHIP_TEMPLATES = {"hms", "uss", "gs", "uscgc", "hmnzs", "ss", "hmcs", "hmas", "fs", "hnlms", "ors"}
RENDERED_TEMPLATES = (
    DATE_TEMPLATES | FIRST_ARGUMENT | SECOND_ARGUMENT | CONVERT | LIST_TEMPLATES | SHIP_TEMPLATES
    | {"start and end dates", "kia"}
)
LIST_MARKERS = {"*", "#"}
KEPT_TAGS = {"b", "i", "strong", "em", "sup", "sub", "blockquote", "ul", "ol", "li"}
LIST_ITEM_TAGS = {"li", "dt", "dd"}
DROPPED_TAGS = {
    "ref", "references", "script", "style", "gallery", "math", "timeline", "score", "templatestyles", "imagemap",
    "hr", "caption",
}
VERBATIM_TAGS = {"nowiki", "pre"}
INTERLANGUAGE = re.compile(r"[a-z]{2,3}(?:-[a-z]+)*")
IMAGE_OPTION = re.compile(
    r"(?:thumb|thumbnail|frame|framed|frameless|border|left|right|center|centre|none|baseline|middle|sub|super"
    r"|text-top|text-bottom|top|bottom|upright|\d*(?:x\d+)?\s*px|(?:alt|link|page|class|lang|upright|thumb"
    r"|thumbnail)\s*=.*)",
    re.IGNORECASE | re.DOTALL,
)
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n\s*")
TAG = re.compile(r"<[^>]*>")
COMMENT = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)
UNUSABLE_FILE_NAME = re.compile(r"\{\{|<|\|")


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def template_name(template: Template) -> str:
    return re.sub(r"[\s_]+", " ", str(template.name).strip().lower())


def plain_text(rendered: str) -> str:
    return html.unescape(TAG.sub("", rendered)).strip()


class _Renderer:
    def __init__(self, battle_index: Mapping[str, str], image_src: Callable[[str, int], str], lang: str = "en"):
        self.lang = lang
        self.battle_index = battle_index
        self.image_src = image_src

    def inline(self, nodes: Iterable) -> str:
        return "".join(self.node(node) for node in nodes)

    def inline_text(self, wikitext: str) -> str:
        return self.inline(mwparserfromhell.parse(wikitext).nodes)

    def node(self, node) -> str:
        if isinstance(node, Text):
            return escape(str(node))
        if isinstance(node, HTMLEntity):
            return escape(node.normalize())
        if isinstance(node, Wikilink):
            return self.wikilink(node)
        if isinstance(node, ExternalLink):
            return self.external_link(node)
        if isinstance(node, Template):
            return self.template(node)
        if isinstance(node, Tag):
            return self.tag(node)
        if isinstance(node, Heading):
            return self.inline(node.title.nodes)
        return ""  # comments, template arguments

    def wikilink(self, node: Wikilink) -> str:
        target = str(node.title).strip()
        if target.startswith(":"):
            target = target[1:].strip()
        else:
            prefix, colon, rest = target.partition(":")
            namespace = prefix.strip().lower()
            if colon and namespace in FILE_NAMESPACES:
                return self.figure(rest.strip(), node.text.nodes if node.text is not None else [])
            if colon and (namespace in CATEGORY_NAMESPACES or INTERLANGUAGE.fullmatch(prefix.strip())):
                return ""
        label = self.inline(node.text.nodes) if node.text is not None else escape(target)
        title = normalize_title(target)
        if not title:
            return label
        fragment = target.partition("#")[2].strip()
        href = wiki_url(title, self.lang)
        if fragment:
            href += "#" + quote(fragment.replace(" ", "_"))
        battle = self.battle_index.get(title)
        battle_attribute = f' data-battle="{escape(battle)}"' if battle else ""
        return f'<a href="{escape(href)}" data-title="{escape(title)}"{battle_attribute}>{label}</a>'

    def figure(self, name: str, text_nodes) -> str:
        name = COMMENT.sub("", name).strip()
        if not name or UNUSABLE_FILE_NAME.search(name):
            return ""
        parts = [[]]
        for node in text_nodes:
            if isinstance(node, Text):
                first, *others = str(node).split("|")
                parts[-1].append(Text(first))
                parts.extend([Text(other)] for other in others)
            else:
                parts[-1].append(node)
        caption, alt = "", None
        for part in parts:
            source = "".join(str(node) for node in part).strip()
            if not source:
                continue
            if IMAGE_OPTION.fullmatch(source):
                key, equals, value = source.partition("=")
                if equals and key.strip().lower() == "alt":
                    alt = plain_text(self.inline_text(value))
            else:
                caption = self.inline(part).strip()
        if alt is None:
            alt = plain_text(caption)
        src = self.image_src(name, IMAGE_WIDTH)
        figcaption = f"<figcaption>{caption}</figcaption>" if caption else ""
        return f'<figure><img src="{escape(src)}" alt="{escape(alt)}" loading="lazy">{figcaption}</figure>'

    def external_link(self, node: ExternalLink) -> str:
        url = str(node.url).strip()
        label = self.inline(node.title.nodes).strip() if node.title is not None else ""
        return f'<a href="{escape(url)}">{label or escape(url)}</a>'

    def template(self, node: Template) -> str:
        name = template_name(node)
        if name not in RENDERED_TEMPLATES:
            return ""  # never touch the arguments of a dropped template
        values = [param.value for param in node.params if not param.showkey]

        def argument(index: int) -> str:
            return self.inline(values[index].nodes).strip() if index < len(values) else ""

        if name in FIRST_ARGUMENT:
            return argument(0)
        if name in SECOND_ARGUMENT:
            return argument(1)
        if name in CONVERT:
            return " ".join(part for part in (argument(0), argument(1)) if part)
        if name == "kia":
            return "†"
        if name in SHIP_TEMPLATES:
            return self.ship(name, argument(0))
        if name in LIST_TEMPLATES:
            return "<br>".join(item for value in values for item in self.list_items(value.nodes))
        numbers = [number for number in (plain_text(argument(i)) for i in range(len(values))) if number.isdigit()]
        if name == "start and end dates":
            if len(numbers) < 6:
                return escape(render_date(numbers[:3]))
            return escape(f"{render_date(numbers[:3])} – {render_date(numbers[3:6])}")
        return escape(render_date(numbers[:3]))

    @staticmethod
    def ship(name: str, ship_name: str) -> str:
        if not ship_name:
            return ""
        if name == "gs":
            prefix = "German submarine" if plain_text(ship_name).startswith("U-") else "German ship"
        elif name == "ss":
            prefix = "SS"
        else:
            prefix = name.upper()
        return f"{prefix} {ship_name}"

    def list_items(self, nodes) -> list[str]:
        """The rendered items of a list argument: one per `*`/`#` item or per line."""
        items = [[]]
        for node in nodes:
            if isinstance(node, Tag) and node.wiki_markup in LIST_MARKERS:
                items.append([])
            elif isinstance(node, Text):
                first, *lines = str(node).split("\n")
                items[-1].append(Text(first))
                items.extend([Text(line)] for line in lines)
            else:
                items[-1].append(node)
        rendered = (self.inline(item).strip() for item in items)
        return [item for item in rendered if plain_text(item) or "<img" in item]

    def tag(self, node: Tag) -> str:
        name = str(node.tag).strip().lower()
        if name in DROPPED_TAGS or (name in LIST_ITEM_TAGS and node.wiki_markup):
            return ""
        if name == "br":
            return "<br>"
        if name == "table":
            return self.table(node)
        if name in VERBATIM_TAGS:
            return escape(str(node.contents or ""))
        inner = self.inline(node.contents.nodes) if node.contents is not None else ""
        if name in KEPT_TAGS:
            return f"<{name}>{inner}</{name}>"
        return inner

    def table(self, node: Tag) -> str:
        rows, loose_cells = [], []
        for child in node.contents.nodes:
            if not isinstance(child, Tag):
                continue
            kind = str(child.tag).strip().lower()
            if kind in ("td", "th") and not str(child).startswith("|+"):
                loose_cells.append(self.cell(child))
            elif kind == "tr":
                if loose_cells:
                    rows.append(loose_cells)
                    loose_cells = []
                rows.append([self.cell(cell) for cell in child.contents.nodes
                             if isinstance(cell, Tag) and str(cell.tag).strip().lower() in ("td", "th")])
        if loose_cells:
            rows.append(loose_cells)
        body = "".join(f"<tr>{''.join(cells)}</tr>" for cells in rows if cells)
        return f'<table class="article-table"><tbody>{body}</tbody></table>'

    def cell(self, node: Tag) -> str:
        kind = str(node.tag).strip().lower()
        return f"<{kind}>{self.inline(node.contents.nodes).strip()}</{kind}>"

    def heading(self, node: Heading) -> str:
        level = "h3" if node.level <= 2 else "h4"
        return f"<{level}>{self.inline(node.title.nodes).strip()}</{level}>"

    def infobox(self, node: Template) -> str:
        fields = {str(param.name).strip().lower(): str(param.value).strip() for param in node.params}
        if template_name(node) in FOREIGN_INFOBOXES:
            return render_plain_infobox(fields, self.inline_text)
        return render_infobox(fields, self.inline_text)

    def block(self, kind: str, payload) -> str:
        if kind == "heading":
            return self.heading(payload)
        if kind == "standalone":
            return self.node(payload)
        if kind == "list":
            return self.list(payload)
        content = self.inline(payload).strip()
        return f"<p>{content}</p>" if plain_text(content) or "<img" in content else ""

    def list(self, items) -> str:
        """Nested <ul>/<ol> from items whose markers (like "*#") give their depth and kind."""
        out, open_lists = [], []
        for markers, nodes in items:
            common = 0
            while common < min(len(open_lists), len(markers)) and open_lists[common] == markers[common]:
                common += 1
            while len(open_lists) > common:
                out.append(f"</li></{_list_tag(open_lists.pop())}>")
            if len(markers) == len(open_lists):
                out.append("</li>")
            for depth, marker in enumerate(markers[common:], common + 1):
                out.append(f"<{_list_tag(marker)}>" + ("" if depth == len(markers) else "<li>"))
                open_lists.append(marker)
            out.append(f"<li>{self.inline(nodes).strip()}")
        while open_lists:
            out.append(f"</li></{_list_tag(open_lists.pop())}>")
        return "".join(out)


def _list_tag(marker: str) -> str:
    return "ul" if marker == "*" else "ol"


def _is_infobox(node) -> bool:
    return isinstance(node, Template) and template_name(node) in INFOBOXES | FOREIGN_INFOBOXES


def _is_standalone(node) -> bool:
    if isinstance(node, Tag):
        return str(node.tag).strip().lower() in ("table", "blockquote")
    if isinstance(node, Wikilink):
        prefix = str(node.title).partition(":")
        return bool(prefix[1]) and prefix[0].strip().lower() in FILE_NAMESPACES
    return False


def _without_dropped_sections(nodes):
    dropped_level = None
    for node in nodes:
        if isinstance(node, Heading):
            if dropped_level is not None and node.level <= dropped_level:
                dropped_level = None
            if dropped_level is None and node.title.strip_code().strip().lower() in DROPPED_SECTIONS:
                dropped_level = node.level
        if dropped_level is None:
            yield node


def _blocks(nodes):
    """(kind, payload) pairs: headings, paragraphs, lists and standalone figures, tables and quotes."""
    paragraph, items, item_open = [], None, False
    for node in nodes:
        is_marker = isinstance(node, Tag) and node.wiki_markup in LIST_MARKERS
        if items is not None and not is_marker and not (item_open or isinstance(node, Text)):
            yield "list", items
            items = None
        if isinstance(node, Heading) or _is_standalone(node) or is_marker:
            if paragraph:
                yield "paragraph", paragraph
                paragraph = []
        if isinstance(node, Heading) or _is_standalone(node):
            if items is not None:
                yield "list", items
                items = None
            yield ("heading" if isinstance(node, Heading) else "standalone"), node
            item_open = False
        elif is_marker:
            items = items or []
            if item_open and not items[-1][1]:
                items[-1][0] += node.wiki_markup
            else:
                items.append([node.wiki_markup, []])
            item_open = True
        elif isinstance(node, Text):
            text = str(node)
            if items is not None:
                if item_open:
                    head, newline, text = text.partition("\n")
                    items[-1][1].append(Text(head))
                    item_open = not newline
                if not text.strip() and "\n" not in text:
                    continue
                yield "list", items
                items = None
                text = text.lstrip("\n")
            first, *others = PARAGRAPH_BREAK.split(text)
            paragraph.append(Text(first))
            for other in others:
                yield "paragraph", paragraph
                paragraph = [Text(other)]
        elif items is not None:
            items[-1][1].append(node)
        else:
            paragraph.append(node)
    if items is not None:
        yield "list", items
    if paragraph:
        yield "paragraph", paragraph


def _fallback(kind: str, payload) -> str:
    """The block's escaped plain text, for when rendering it failed."""
    try:
        if kind == "list":
            source = "\n".join("".join(str(node) for node in nodes) for _, nodes in payload)
        elif kind in ("heading", "standalone"):
            source = str(payload)
        else:
            source = "".join(str(node) for node in payload)
        text = mwparserfromhell.parse(source).strip_code().strip()
        return f"<p>{escape(text)}</p>" if text else ""
    except Exception as error:
        LOG.warning("A %s block is left out: %r", kind, error, exc_info=error)
        return ""


def render_article(
    wikitext: str, *, battle_index: Mapping[str, str], image_src: Callable[[str, int], str], lang: str = "en"
) -> str:
    """Sanitised HTML for an Artikel: its own infobox first, then the body without reference sections."""
    renderer = _Renderer(battle_index, image_src, lang)
    nodes = list(mwparserfromhell.parse(wikitext).nodes)
    parts = []
    infobox = next((node for node in nodes if _is_infobox(node)), None)
    if infobox is not None:
        nodes.remove(infobox)
        try:
            parts.append(renderer.infobox(infobox))
        except Exception as error:
            LOG.warning("Infobox could not be rendered and is left out: %r", error, exc_info=error)
    for kind, payload in _blocks(_without_dropped_sections(nodes)):
        try:
            parts.append(renderer.block(kind, payload))
        except Exception as error:
            LOG.warning("A %s block fell back to plain text: %r", kind, error, exc_info=error)
            parts.append(_fallback(kind, payload))
    return sanitize("".join(parts))

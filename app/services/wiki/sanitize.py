"""The whitelist every rendered Artikel passes before it reaches the page."""

import nh3

TAGS = {
    "a", "b", "i", "em", "strong", "p", "br", "h3", "h4", "ul", "ol", "li", "figure", "figcaption", "img",
    "table", "thead", "tbody", "tr", "th", "td", "sup", "sub", "blockquote", "span",
}
TABLE_ATTRIBUTES = {"class", "colspan", "rowspan"}
ATTRIBUTES = {
    "a": {"href", "data-title", "data-battle", "class"},
    "img": {"src", "alt", "loading", "width"},
    "table": TABLE_ATTRIBUTES,
    "td": TABLE_ATTRIBUTES,
    "th": TABLE_ATTRIBUTES,
    "span": TABLE_ATTRIBUTES,
}
# Relative URLs (the cached images under /api/battles/images/) pass through as well.
URL_SCHEMES = {"http", "https"}


def sanitize(html: str) -> str:
    """Keep only whitelisted tags, attributes and URL schemes."""
    return nh3.clean(html, tags=TAGS, attributes=ATTRIBUTES, url_schemes=URL_SCHEMES, link_rel=None)

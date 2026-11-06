import re
from urllib.parse import unquote


def normalize_title(raw: str) -> str:
    """Bring a Wikipedia title or link target to the form used for lookups."""
    title = unquote(raw).replace("_", " ")
    title = title.split("#", 1)[0]
    title = re.sub(r"\s+", " ", title).strip()
    return title[:1].upper() + title[1:]

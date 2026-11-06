import asyncio
import hashlib
import os
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

import requests
from wireup import injectable

from app.core.config import settings
from app.services.scraping.uboat_net.http_client import build_user_agent

ALLOWED_WIDTHS = (330, 500, 960)
ALLOWED_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".tif", ".tiff", ".webp")
FETCH_TIMEOUT_SECONDS = 20
FAILURE_MEMORY_SECONDS = 3600
TRANSIENT_BACKOFF_SECONDS = 60
MAX_REMEMBERED_FAILURES = 10_000
MAX_NAME_BYTES = 200
REPOSITORIES = ("commons", "en")

# Fetches one URL: the image bytes, or None when the server has no such image.
# A throttled or failing server raises TransientFetchError; any other exception is transient too.
Fetch = Callable[[str], bytes | None]


class TransientFetchError(Exception):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def snap_width(width: int) -> int:
    for allowed in ALLOWED_WIDTHS:
        if width <= allowed:
            return allowed
    return ALLOWED_WIDTHS[-1]


def normalise_name(file_name: str) -> str:
    """The name the way Wikimedia stores it: underscores, first letter upper-cased."""
    name = file_name.strip().replace(" ", "_")
    return name[:1].upper() + name[1:]


def is_servable_name(file_name: str) -> bool:
    """Only plain image file names; a path or control character never reaches the disk or the network."""
    name = normalise_name(file_name)
    if len(name.encode()) > MAX_NAME_BYTES or not name.lower().endswith(ALLOWED_SUFFIXES):
        return False
    return not any(c in name for c in "/\\") and name.isprintable() and not name.startswith(".")


def image_url_for(file_name: str, width: int) -> str:
    return f"/api/battles/images/{quote(normalise_name(file_name))}?width={snap_width(width)}"


def thumbnail_urls(file_name: str, width: int) -> list[str]:
    name = normalise_name(file_name)
    md5 = hashlib.md5(name.encode()).hexdigest()
    quoted = quote(name)
    suffix = ".png" if name.lower().endswith(".svg") else ""
    return [
        f"https://upload.wikimedia.org/wikipedia/{repo}/thumb/{md5[0]}/{md5[:2]}/{quoted}/{width}px-{quoted}{suffix}"
        for repo in REPOSITORIES
    ]


def _session_fetch() -> Fetch:
    session = requests.Session()
    session.headers["User-Agent"] = build_user_agent(settings.CRAWLER_CONTACT)

    def fetch(url: str) -> bytes | None:
        response = session.get(url, timeout=FETCH_TIMEOUT_SECONDS)
        if response.status_code == 404:
            return None
        if response.status_code == 429 or response.status_code >= 500:
            retry_after = response.headers.get("Retry-After", "")
            raise TransientFetchError(
                f"HTTP {response.status_code}", float(retry_after) if retry_after.isdigit() else None
            )
        response.raise_for_status()
        return response.content

    return fetch


@injectable
class ImageCache:
    """Wikimedia thumbnails, fetched once and then served from disk."""

    def __init__(self, fetch: Fetch | None = None, directory: Path | None = None):
        self._fetch = fetch or _session_fetch()
        self._directory = directory or Path(settings.WIKI_IMAGE_DIR).expanduser()
        self._lock = asyncio.Lock()
        self._retry_at: dict[tuple[str, int], float] = {}

    async def get(self, file_name: str, width: int) -> Path | None:
        if not is_servable_name(file_name):
            return None
        name = normalise_name(file_name)
        width = snap_width(width)
        md5 = hashlib.md5(name.encode()).hexdigest()
        path = self._directory / str(width) / md5[:2] / name
        if path.is_file():
            return path
        key = (name, width)
        async with self._lock:
            if path.is_file():
                return path
            retry_at = self._retry_at.get(key)
            if retry_at is not None and time.monotonic() < retry_at:
                return None
            outcome = await asyncio.to_thread(self._download, name, width)
            if isinstance(outcome, bytes):
                self._retry_at.pop(key, None)
                await asyncio.to_thread(_write_atomically, path, outcome)
                return path
            self._remember_failure(key, outcome)
            return None

    def _remember_failure(self, key: tuple[str, int], seconds: float) -> None:
        now = time.monotonic()
        self._retry_at = {k: t for k, t in self._retry_at.items() if t > now}
        while len(self._retry_at) >= MAX_REMEMBERED_FAILURES:
            del self._retry_at[next(iter(self._retry_at))]
        self._retry_at[key] = now + seconds

    def _download(self, name: str, width: int) -> bytes | float:
        """The image bytes, or else how many seconds to remember that there are none."""
        backoff = None
        for url in thumbnail_urls(name, width):
            try:
                data = self._fetch(url)
            except Exception as error:  # noqa: BLE001 - a timeout or network error is transient
                retry_after = getattr(error, "retry_after", None)
                wait = min(retry_after or TRANSIENT_BACKOFF_SECONDS, FAILURE_MEMORY_SECONDS)
                backoff = max(backoff or 0, wait)
                continue
            if data:
                return data
        return FAILURE_MEMORY_SECONDS if backoff is None else backoff


def _write_atomically(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)

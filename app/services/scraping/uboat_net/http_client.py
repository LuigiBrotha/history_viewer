import time

import requests

BASE_URL = "https://uboat.net"

_DEFAULT_USER_AGENT = "uboats-scraper/0.1"

# Without a timeout a dead connection hangs the crawl; IPv6 to uboat.net can stall
# in SYN-SENT for about two minutes before falling back to IPv4.
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 60


def build_user_agent(contact: str | None) -> str:
    if contact:
        return f"{_DEFAULT_USER_AGENT} (+contact: {contact})"
    return _DEFAULT_USER_AGENT


class PoliteHttpClient:
    def __init__(self, delay_seconds: float, user_agent: str):
        self._delay_seconds = delay_seconds
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._last_request_at: float | None = None

    def get_text(self, url: str) -> str:
        self._wait_for_slot()
        try:
            response = self._session.get(url, timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS))
        finally:
            # A fast failure must still honour the delay before the next request.
            self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response.text

    def _wait_for_slot(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

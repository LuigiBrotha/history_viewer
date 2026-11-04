from urllib.parse import urlsplit

from fastapi import HTTPException, Request

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
LOCAL_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
# A proxy or a spoofing client may have rewritten the peer address; refuse to edit through any of them.
FORWARDING_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip")


def _hostname(value: str) -> str | None:
    try:
        return urlsplit(f"//{value}").hostname
    except ValueError:
        return None


def is_loopback(request: Request | None) -> bool:
    """True when this request may edit: from this machine, addressed to it, and not forwarded.

    Checks the socket peer, rejects forwarding headers outright (uvicorn may rewrite the peer
    from them), and requires Host and, when present, Origin to name this machine, which
    stops DNS rebinding from a web page in a local browser.
    """
    client = getattr(request, "client", None)
    if client is None or client.host not in LOOPBACK_HOSTS:
        return False
    headers = request.headers
    if any(headers.get(name) is not None for name in FORWARDING_HEADERS):
        return False
    host = headers.get("host")
    if host is None or _hostname(host) not in LOCAL_NAMES:
        return False
    origin = headers.get("origin")
    if origin is not None:
        try:
            origin_host = urlsplit(origin).hostname
        except ValueError:
            return False
        if origin_host not in LOCAL_NAMES:
            return False
    return True


def require_loopback(request: Request) -> None:
    if not is_loopback(request):
        raise HTTPException(status_code=403, detail="Editing is only allowed from this computer")

from fastapi import HTTPException, Request

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})


def is_loopback(request: Request | None) -> bool:
    """True when the socket peer is this machine. Forwarding headers are deliberately ignored."""
    client = getattr(request, "client", None)
    return client is not None and client.host in LOOPBACK_HOSTS


def require_loopback(request: Request) -> None:
    if not is_loopback(request):
        raise HTTPException(status_code=403, detail="Editing is only allowed from this computer")

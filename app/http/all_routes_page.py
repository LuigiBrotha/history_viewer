from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from wireup.integration.fastapi import WireupRoute

from app.core.config import FRONTEND_DIR


def _with_query(path: str, request: Request) -> RedirectResponse:
    query = request.url.query
    return RedirectResponse(f"{path}?{query}" if query else path)


class RequestHandler:
    router = APIRouter(route_class=WireupRoute)

    @router.get("/", include_in_schema=False)
    async def handle_request(self, request: Request) -> Response:
        # A link from when the timeline was here: only that page has a date.
        if "datum" in request.query_params:
            return _with_query("dag-tot-dag", request)
        return FileResponse(FRONTEND_DIR / "index.html")

    @router.get("/status", include_in_schema=False)
    async def old_address(self, request: Request) -> RedirectResponse:
        return _with_query("./", request)

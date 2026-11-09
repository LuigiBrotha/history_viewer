from fastapi import APIRouter
from fastapi.responses import FileResponse
from wireup.integration.fastapi import WireupRoute

from app.core.config import FRONTEND_DIR


class RequestHandler:
    router = APIRouter(route_class=WireupRoute)

    @router.get("/dag-tot-dag", include_in_schema=False)
    async def handle_request(self) -> FileResponse:
        return FileResponse(FRONTEND_DIR / "dag-tot-dag.html")

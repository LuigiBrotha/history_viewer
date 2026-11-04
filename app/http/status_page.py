from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import FRONTEND_DIR


class RequestHandler:
    router = APIRouter()

    @router.get("/status", include_in_schema=False)
    async def handle_request(self) -> FileResponse:
        return FileResponse(FRONTEND_DIR / "status.html")

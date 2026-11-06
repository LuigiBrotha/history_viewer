from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from wireup import Inject
from wireup.integration.fastapi import WireupRoute

from app.services.wiki.image_cache import ImageCache, is_servable_name

IMMUTABLE = "max-age=31536000, immutable"


class RequestHandler:
    router = APIRouter(tags=["api"], route_class=WireupRoute)

    def __init__(self, images: Annotated[ImageCache, Inject()]):
        self.images = images

    @router.get("/api/battles/images/{file_name:path}", name="battles_image")
    async def handle_request(self, file_name: str, width: int = 330) -> FileResponse:
        path = await self.images.get(file_name, width) if is_servable_name(file_name) else None
        if path is None:
            raise HTTPException(status_code=404, detail="Geen afbeelding.")
        # An SVG is stored as the PNG rendering that Wikimedia serves for it.
        media_type = "image/png" if file_name.lower().endswith(".svg") else None
        return FileResponse(path, media_type=media_type, headers={"Cache-Control": IMMUTABLE})

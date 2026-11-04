from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
import wireup.integration.fastapi
from fastapi.staticfiles import StaticFiles
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import settings
from app.core.container import container
from app.core.database import engine
from app.services.storage.database import init_models
from fastapi import FastAPI

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_models(engine)
    # A mount at "/" matches every path, so it must follow the API routes. Wireup registers
    # class-based handlers during its own lifespan, which runs before this one.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    yield
    await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    debug=settings.DEBUG,
)

with async_container_force_sync_scope(container) as scope:
    request_handler_registry = scope.get(RequestHandlerRegistry)
    handlers = list(request_handler_registry)

wireup.integration.fastapi.setup(container, app, class_based_handlers=handlers)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

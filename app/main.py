from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
import wireup.integration.fastapi
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import FRONTEND_DIR, settings
from app.core.container import container
from app.core.database import engine
from app.services.storage.database import init_models
from fastapi import FastAPI


class RevalidateMiddleware:
    """Makes browsers check every response, so an update never mixes old and new modules."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def send_with_header(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((b"cache-control", b"no-cache"))
            await send(message)

        if scope["type"] == "http":
            await self.app(scope, receive, send_with_header)
        else:
            await self.app(scope, receive, send)


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

app.add_middleware(RevalidateMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

wireup.integration.fastapi.setup(container, app, class_based_handlers=handlers)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, proxy_headers=False)

import uvicorn
import wireup.integration.fastapi
from wireup.ioc.container.async_container import async_container_force_sync_scope

from app.services.request_handler_registry import RequestHandlerRegistry
from app.core.config import settings
from app.core.container import container
from fastapi import FastAPI

app = FastAPI(
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

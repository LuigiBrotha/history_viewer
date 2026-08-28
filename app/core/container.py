import wireup
import app.core
import app.services
import app.http
import wireup.integration.fastapi

from app.core.config import settings

container = wireup.create_async_container(
    injectables=[wireup.integration.fastapi.request_factory, app.core, app.services, app.http],
    config=settings,
)

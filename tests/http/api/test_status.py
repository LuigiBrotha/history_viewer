from app.http.api.uboats.status import RequestHandler
from app.services.export.uboats import CrawlStatusOut
from app.services.storage.crawl_status_repository import CrawlStatusRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def test_handle_request_returns_crawl_status(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    empty = await RequestHandler(session_factory).handle_request()
    assert empty == CrawlStatusOut(None, 0, 0, 0, None, None)
    assert empty.first_departure is None and empty.last_departure is None

    async with session_factory() as session:
        await CrawlStatusRepository(session).set_listing_total(5)

    result = await RequestHandler(session_factory).handle_request()
    assert result.listing_total == 5

    await engine.dispose()

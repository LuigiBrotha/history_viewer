from contextlib import asynccontextmanager

from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


@asynccontextmanager
async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def test_record_success_sets_status_and_timestamps(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = BoatCrawlStateRepository(session)
            await repo.record_success("u99")
            state = await repo.get("u99")

    assert state.status == "success"
    assert state.last_success_at is not None
    assert state.last_attempt_at is not None
    assert state.last_error is None


async def test_record_failure_sets_status_and_error(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = BoatCrawlStateRepository(session)
            await repo.record_failure("u99", "connection timed out")
            state = await repo.get("u99")

    assert state.status == "failed"
    assert state.last_error == "connection timed out"
    assert state.last_success_at is None


async def test_get_returns_none_for_unknown_slug(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            state = await BoatCrawlStateRepository(session).get("unknown")

    assert state is None


async def test_success_after_failure_clears_error_and_sets_success(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = BoatCrawlStateRepository(session)
            await repo.record_failure("u99", "boom")
            await repo.record_success("u99")
            session.expire_all()
            state = await repo.get("u99")

    assert state.status == "success"
    assert state.last_error is None

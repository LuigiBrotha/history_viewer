import pytest

from app.services.storage.database import create_engine, create_session_factory, init_models


@pytest.fixture
async def session_factory(tmp_path):
    """A fresh SQLite database for one test, closed afterwards so no aiosqlite thread outlives the event loop."""
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    yield create_session_factory(engine)
    await engine.dispose()

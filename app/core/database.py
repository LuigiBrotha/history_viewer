from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wireup import injectable

from app.core.config import settings
from app.services.storage.database import create_engine, create_session_factory

engine = create_engine(settings.DATABASE_URL)
_session_factory = create_session_factory(engine)


@injectable
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory

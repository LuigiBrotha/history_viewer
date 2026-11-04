from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.services.storage.models import Base, Patrol


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_patrol_columns)


def _add_missing_patrol_columns(sync_conn) -> None:
    # create_all never alters existing tables, so databases created before these
    # columns existed get them added here.
    existing = {row[1] for row in sync_conn.execute(text("PRAGMA table_info(patrols)"))}
    for column in Patrol.__table__.columns:
        if column.name in ("crawled_at", "updated_at") and column.name not in existing:
            sync_conn.execute(text(f"ALTER TABLE patrols ADD COLUMN {column.name} DATETIME"))

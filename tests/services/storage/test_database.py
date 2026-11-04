from datetime import date

from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Boat, BoatCrawlState, Patrol, RoutePoint


async def test_init_models_creates_tables_and_boat_round_trips(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        session.add(Boat(
            slug="u99",
            number="U-99",
            type="VIIB",
            builder="F. Krupp Germaniawerft AG, Kiel",
            laid_down=date(1939, 3, 31),
            launched=date(1940, 3, 12),
            commissioned=date(1940, 4, 18),
            fate="Scuttled",
        ))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(Boat.__table__.select())
        row = result.first()

    assert row.slug == "u99"
    assert row.laid_down == date(1939, 3, 31)

    await engine.dispose()


async def test_patrol_and_route_point_round_trip_via_foreign_key(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        boat = Boat(slug="u99", number="U-99")
        session.add(boat)
        await session.flush()
        patrol = Patrol(boat_id=boat.id, external_id="patrol_4754", patrol_number=1)
        session.add(patrol)
        await session.flush()
        session.add(RoutePoint(patrol_id=patrol.id, sequence=0, lat=54.3667, lng=10.1667, date=date(1940, 6, 18)))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(RoutePoint.__table__.select())
        row = result.first()

    assert row.lat == 54.3667
    assert row.date == date(1940, 6, 18)

    await engine.dispose()


async def test_boat_crawl_state_round_trip(tmp_path):
    from datetime import datetime, timezone

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        session.add(BoatCrawlState(slug="u99", status="success", last_attempt_at=now, last_success_at=now))
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(BoatCrawlState.__table__.select())
        row = result.first()

    assert row.status == "success"
    assert row.last_attempt_at.tzinfo is not None

    await engine.dispose()


async def test_init_models_adds_missing_patrol_columns_to_an_existing_database(tmp_path):
    from sqlalchemy import text

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE boats (id INTEGER PRIMARY KEY, slug VARCHAR NOT NULL, number VARCHAR NOT NULL)"))
        await conn.execute(text(
            "CREATE TABLE patrols (id INTEGER PRIMARY KEY, boat_id INTEGER NOT NULL, "
            "external_id VARCHAR NOT NULL UNIQUE, patrol_number INTEGER NOT NULL)"
        ))
        await conn.execute(text("INSERT INTO patrols (boat_id, external_id, patrol_number) VALUES (1, 'old', 1)"))

    await init_models(engine)
    await init_models(engine)  # idempotent

    async with engine.connect() as conn:
        columns = {row[1] for row in (await conn.execute(text("PRAGMA table_info(patrols)"))).all()}
        row = (await conn.execute(text("SELECT external_id, crawled_at, updated_at FROM patrols"))).one()

    assert {"crawled_at", "updated_at"} <= columns
    assert tuple(row) == ("old", None, None)

    await engine.dispose()

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import update

from app.http.api.uboats.ships import RequestHandler
from app.services.scraping.uboat_net.types import ShipHitRef
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import ShipHit
from app.services.storage.ship_hit_repository import ShipHitRepository


def _ref(ship_id):
    return ShipHitRef(
        ship_id, "u99", f"Ship {ship_id}", date(1940, 7, 5), 2053, "ca", "HX-52", "sunk",
        f"https://uboat.net/allies/merchants/ship/{ship_id}.html",
    )


async def test_handle_request_returns_ship_hits(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        await ShipHitRepository(session).upsert_refs([_ref("408")])

    result = await RequestHandler(session_factory).handle_request()

    assert [(h.name, h.boat_slug, h.outcome, h.lat) for h in result] == [("Ship 408", "u99", "sunk", None)]
    await engine.dispose()


async def test_ships_since_returns_only_changed_hits(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    cursor = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)
    async with session_factory() as session:
        await ShipHitRepository(session).upsert_refs([_ref("old"), _ref("new")])
        for ship_id, stamp in [("old", cursor - timedelta(hours=1)), ("new", cursor + timedelta(hours=1))]:
            await session.execute(update(ShipHit).where(ShipHit.ship_external_id == ship_id).values(updated_at=stamp))
        await session.commit()

    result = await RequestHandler(session_factory).handle_request(since=cursor)

    assert [h.ship_external_id for h in result] == ["new"]
    await engine.dispose()

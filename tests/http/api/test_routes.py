from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.http.api.uboats.routes import RequestHandler
from app.services.scraping.uboat_net.types import BoatData, PatrolDetail, PatrolSummary, RoutePointData
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Patrol
from app.services.storage.patrol_repository import PatrolRepository


async def test_handle_request_returns_patrol_routes(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        boat_repo = BoatRepository(session)
        await boat_repo.upsert_boat(BoatData(
            slug="u99", number="U-99", type=None, builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))
        boat_id = await boat_repo.get_id_by_slug("u99")
        summary = PatrolSummary(
            external_id="patrol_4754", patrol_number=1, commander=None,
            departure_port="Kiel", departure_date=None, arrival_port="Wilhelmshaven", arrival_date=None,
            days_at_sea=8, tonnage=None, detail_url="https://uboat.net/boats/patrols/patrol_4754.html",
        )
        detail = PatrolDetail(description=None, route_points=[RoutePointData(0, 54.3667, 10.1667, None)])
        await PatrolRepository(session).upsert_patrol(boat_id, summary, detail)

    result = await RequestHandler(session_factory).handle_request()

    assert len(result) == 1
    assert result[0].boat_slug == "u99"
    assert len(result[0].points) == 1

    await engine.dispose()


async def test_handle_request_since_filters_to_changed_patrols(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    cursor = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        boat_repo = BoatRepository(session)
        await boat_repo.upsert_boat(BoatData(
            slug="u99", number="U-99", type=None, builder=None,
            laid_down=None, launched=None, commissioned=None, fate=None,
        ))
        boat_id = await boat_repo.get_id_by_slug("u99")
        for external_id, stamp in [("old", cursor - timedelta(hours=1)), ("new", cursor + timedelta(hours=1))]:
            summary = PatrolSummary(
                external_id=external_id, patrol_number=1, commander=None,
                departure_port=None, departure_date=None, arrival_port=None, arrival_date=None,
                days_at_sea=None, tonnage=None, detail_url=f"https://uboat.net/boats/patrols/{external_id}.html",
            )
            await PatrolRepository(session).upsert_patrol(boat_id, summary, PatrolDetail(None, []))
            await session.execute(update(Patrol).where(Patrol.external_id == external_id).values(updated_at=stamp))
        await session.commit()

    result = await RequestHandler(session_factory).handle_request(since=cursor)

    assert [r.external_id for r in result] == ["new"]

    await engine.dispose()

from datetime import date

from app.http.api.uboats.patrol_periods import RequestHandler
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Boat, Patrol


async def test_only_patrols_with_both_dates_are_returned(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        boat = Boat(slug="u99", number="U-99")
        boat.patrols = [
            Patrol(external_id="a", patrol_number=1, departure_date=date(1940, 6, 18), arrival_date=date(1940, 7, 25)),
            Patrol(external_id="b", patrol_number=2, departure_date=date(1940, 8, 4), arrival_date=None),
        ]
        session.add(boat)
        await session.commit()

    result = await RequestHandler(session_factory).handle_request()

    assert [(p.departure_date, p.arrival_date) for p in result] == [(date(1940, 6, 18), date(1940, 7, 25))]
    await engine.dispose()

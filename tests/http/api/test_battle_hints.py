import json
from datetime import datetime, timezone

from app.http.api.battles.hints import RequestHandler
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import BattleHints

HINTS = [{"name": "Bir Hakeim", "lat": 31.6, "lng": 23.48, "kind": "infobox"},
         {"name": "Tobruk", "lat": 32.08, "lng": 23.97, "kind": "artikel"}]


async def test_the_plaatshints_of_a_battle_and_none_for_another(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add(BattleHints(battle="Battle of Bir Hakeim", hints_json=json.dumps(HINTS),
                                computed_at=datetime.now(timezone.utc)))
        await session.commit()
    handler = RequestHandler(factory)
    found = await handler.handle_request("Battle of Bir Hakeim")
    assert [hint.model_dump() for hint in found.hints] == HINTS
    assert (await handler.handle_request("Battle of Nowhere")).hints == []
    await engine.dispose()

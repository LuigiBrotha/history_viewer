import json
import os

from app.services.battles.known_battles import known_battle_titles
from app.services.storage.battle_position_repository import BattlePositionRepository
from app.services.storage.database import create_engine, create_session_factory, init_models


async def make_sf(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return engine, create_session_factory(engine)


async def test_put_then_all(tmp_path):
    engine, sf = await make_sf(tmp_path)
    async with sf() as session:
        await BattlePositionRepository(session).put("A", 1.5, 2.5)
        assert await BattlePositionRepository(session).all() == [("A", 1.5, 2.5)]
    await engine.dispose()


async def test_put_again_replaces(tmp_path):
    engine, sf = await make_sf(tmp_path)
    async with sf() as session:
        repo = BattlePositionRepository(session)
        await repo.put("A", 1.0, 2.0)
        await repo.put("A", 3.0, 4.0)
        assert await repo.all() == [("A", 3.0, 4.0)]
    await engine.dispose()


async def test_delete_removes_and_tolerates_absent(tmp_path):
    engine, sf = await make_sf(tmp_path)
    async with sf() as session:
        repo = BattlePositionRepository(session)
        await repo.put("A", 1.0, 2.0)
        await repo.delete("A")
        assert await repo.all() == []
        await repo.delete("A")
    await engine.dispose()


def test_known_battle_titles_rereads_when_the_file_changes(tmp_path):
    path = tmp_path / "battles.json"
    path.write_text(json.dumps([{"title": "A"}]), encoding="utf-8")
    assert known_battle_titles(path) == frozenset({"A"})

    path.write_text(json.dumps([{"title": "A"}, {"title": "B"}]), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    assert known_battle_titles(path) == frozenset({"A", "B"})

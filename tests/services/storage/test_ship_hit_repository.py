from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import update

from app.services.scraping.uboat_net.types import BoatData, ShipDetails, ShipHitRef
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import ShipHit
from app.services.storage.ship_detail_repository import ShipDetailRepository
from app.services.storage.ship_hit_repository import ShipHitRepository


@asynccontextmanager
async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def _ref(ship_id="408", slug="u99", name="Magog", day=date(1940, 7, 5), outcome="sunk", tons=2053):
    return ShipHitRef(
        ship_id, slug, name, day, tons, "ca", "HX-52", outcome,
        f"https://uboat.net/allies/merchants/ship/{ship_id}.html",
    )


async def test_upsert_refs_keeps_a_stored_position(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = ShipHitRepository(session)
            await repo.upsert_refs([_ref()])
            [pending] = await repo.pending_pages()
            await repo.set_position(pending.id, (50.5, -11.0))
            await ShipDetailRepository(session).save("408", ShipDetails())
            await repo.upsert_refs([_ref(tons=2054)])
            [hit] = await repo.list_hits()
            still_pending = await repo.pending_pages()

    assert (hit.lat, hit.lng, hit.tons) == (50.5, -11.0, 2054)
    assert still_pending == []


async def test_upsert_refs_of_unchanged_hits_does_not_move_updated_at(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = ShipHitRepository(session)
            await repo.upsert_refs([_ref()])
            [first] = await repo.list_hits()
            await repo.upsert_refs([_ref()])
            [second] = await repo.list_hits()

    assert first.updated_at == second.updated_at


async def test_same_ship_hit_twice_is_stored_twice(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = ShipHitRepository(session)
            await repo.upsert_refs([
                _ref(outcome="damaged"),
                _ref(day=date(1940, 7, 9), outcome="sunk"),
                _ref(slug="u100"),
            ])
            hits = await repo.list_hits()

    assert [(h.boat_slug, h.date, h.outcome) for h in hits] == [
        ("u99", date(1940, 7, 5), "damaged"),
        ("u100", date(1940, 7, 5), "sunk"),
        ("u99", date(1940, 7, 9), "sunk"),
    ]


async def test_hits_carry_the_boat_number(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            await BoatRepository(session).upsert_boat(BoatData(
                slug="u99", number="U-99", type=None, builder=None,
                laid_down=None, launched=None, commissioned=None, fate=None,
            ))
            repo = ShipHitRepository(session)
            await repo.upsert_refs([_ref(), _ref(ship_id="9", slug="u1234")])
            hits = {h.boat_slug: h for h in await repo.list_hits()}

    assert hits["u99"].boat_number == "U-99"
    assert hits["u1234"].boat_number == "U-1234"  # boat not in the database: derived from the slug


async def test_ship_without_a_position_is_not_retried_unless_forced(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = ShipHitRepository(session)
            await repo.upsert_refs([_ref()])
            [pending] = await repo.pending_pages()
            await repo.set_position(pending.id, None)
            await ShipDetailRepository(session).save("408", ShipDetails())

            normal = await repo.pending_pages()
            forced = await repo.pending_pages(force=True)
            other_boat = await repo.pending_pages(force=True, slugs=["u1"])
            [hit] = await repo.list_hits()

    assert normal == []
    assert [h.ship_external_id for h in forced] == ["408"]
    assert other_boat == []
    assert (hit.lat, hit.lng) == (None, None)


async def test_ships_since_returns_only_changed_hits(tmp_path):
    cursor = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = ShipHitRepository(session)
            await repo.upsert_refs([_ref(ship_id="old"), _ref(ship_id="new")])
            for ship_id, stamp in [("old", cursor - timedelta(hours=1)), ("new", cursor + timedelta(hours=1))]:
                await session.execute(update(ShipHit).where(ShipHit.ship_external_id == ship_id).values(updated_at=stamp))
            await session.commit()

            changed = await repo.list_hits(since=cursor)

    assert [h.ship_external_id for h in changed] == ["new"]


async def test_hit_with_a_position_but_no_details_is_pending(tmp_path):
    async with _session_factory(tmp_path) as session_factory:
        async with session_factory() as session:
            repo = ShipHitRepository(session)
            await repo.upsert_refs([_ref(), _ref(slug="u100")])
            for hit in await repo.pending_pages():
                await repo.set_position(hit.id, (50.5, -11.0))
            without_details = await repo.pending_pages()
            await ShipDetailRepository(session).save("408", ShipDetails())
            with_details = await repo.pending_pages()

    assert [h.boat_slug for h in without_details] == ["u99", "u100"]
    assert with_details == []

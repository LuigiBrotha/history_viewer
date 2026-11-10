from datetime import date

from app.services.scraping.uboat_net.types import BoatData
from app.services.storage.boat_repository import BoatRepository
def _boat_data(slug="u99", **overrides):
    defaults = dict(
        slug=slug,
        number="U-99",
        type="VIIB",
        builder="F. Krupp Germaniawerft AG, Kiel",
        laid_down=date(1939, 3, 31),
        launched=date(1940, 3, 12),
        commissioned=date(1940, 4, 18),
        fate="Scuttled",
    )
    defaults.update(overrides)
    return BoatData(**defaults)


async def test_upsert_boat_inserts_new_boat(session_factory):

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(_boat_data())
        summaries = await BoatRepository(session).list_summaries()

    assert len(summaries) == 1
    assert summaries[0].slug == "u99"
    assert summaries[0].number == "U-99"
    assert summaries[0].patrol_count == 0


async def test_upsert_boat_updates_existing_row_on_conflict(session_factory):

    async with session_factory() as session:
        repo = BoatRepository(session)
        await repo.upsert_boat(_boat_data(fate="Scuttled"))
        await repo.upsert_boat(_boat_data(fate="Sunk by depth charges"))
        summaries = await repo.list_summaries()

    assert len(summaries) == 1
    assert summaries[0].fate == "Sunk by depth charges"


async def test_get_id_by_slug_returns_none_for_unknown_slug(session_factory):

    async with session_factory() as session:
        boat_id = await BoatRepository(session).get_id_by_slug("unknown")

    assert boat_id is None


async def test_get_id_by_slug_returns_id_after_upsert(session_factory):

    async with session_factory() as session:
        repo = BoatRepository(session)
        await repo.upsert_boat(_boat_data())
        boat_id = await repo.get_id_by_slug("u99")

    assert isinstance(boat_id, int)


async def test_get_detail_returns_none_for_unknown_slug(session_factory):

    async with session_factory() as session:
        detail = await BoatRepository(session).get_detail("unknown")

    assert detail is None


async def test_get_detail_returns_boat_fields_and_empty_patrols(session_factory):

    async with session_factory() as session:
        await BoatRepository(session).upsert_boat(_boat_data())
        detail = await BoatRepository(session).get_detail("u99")

    assert detail.slug == "u99"
    assert detail.type == "VIIB"
    assert detail.laid_down == date(1939, 3, 31)
    assert detail.patrols == []


async def test_list_summaries_orders_by_slug(session_factory):

    async with session_factory() as session:
        repo = BoatRepository(session)
        await repo.upsert_boat(_boat_data(slug="u255", number="U-255"))
        await repo.upsert_boat(_boat_data(slug="u99", number="U-99"))
        summaries = await repo.list_summaries()

    assert [s.slug for s in summaries] == ["u255", "u99"]

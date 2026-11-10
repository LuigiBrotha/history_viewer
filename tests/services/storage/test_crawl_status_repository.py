from sqlalchemy import update

from app.services.export.uboats import CrawlStatusOut
from app.services.scraping.uboat_net.types import PatrolDetail, PatrolSummary
from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.crawl_status_repository import CrawlStatusRepository
from app.services.storage.models import Patrol
from app.services.storage.patrol_repository import PatrolRepository
from app.services.scraping.uboat_net.types import BoatData


async def _store_patrol(session, slug, number, external_id):
    boats = BoatRepository(session)
    await boats.upsert_boat(BoatData(
        slug=slug, number=number, type=None, builder=None,
        laid_down=None, launched=None, commissioned=None, fate=None,
    ))
    boat_id = await boats.get_id_by_slug(slug)
    summary = PatrolSummary(
        external_id=external_id, patrol_number=1, commander=None, departure_port=None,
        departure_date=None, arrival_port=None, arrival_date=None, days_at_sea=None,
        tonnage=None, detail_url="https://uboat.net/x.html",
    )
    await PatrolRepository(session).upsert_patrol(boat_id, summary, PatrolDetail(description=None, route_points=[]))


async def test_get_status_on_an_empty_database(session_factory):
    async with session_factory() as session:
        status = await CrawlStatusRepository(session).get_status()

    assert status == CrawlStatusOut(None, 0, 0, 0, None, None)


async def test_get_status_reports_the_newest_crawled_patrol(session_factory):
    async with session_factory() as session:
        await _store_patrol(session, "u1", "U-1", "legacy")
        await session.execute(update(Patrol).values(crawled_at=None, updated_at=None))
        await session.commit()
        await _store_patrol(session, "u2", "U-2", "first")
        await _store_patrol(session, "u3", "U-3", "second")
        repo = CrawlStatusRepository(session)
        await repo.set_listing_total(1153)
        status = await repo.get_status()

    assert status.listing_total == 1153
    assert status.last_patrol.external_id == "second"
    assert status.last_patrol.boat_slug == "u3"
    assert status.last_patrol.boat_number == "U-3"
    assert status.revision == status.last_patrol.crawled_at
    assert status.patrol_count == 3


async def test_set_listing_total_overwrites_the_previous_value(session_factory):
    async with session_factory() as session:
        repo = CrawlStatusRepository(session)
        await repo.set_listing_total(10)
        await repo.set_listing_total(20)
        assert (await repo.get_status()).listing_total == 20


async def test_get_status_counts_success_and_failure_separately(session_factory):
    async with session_factory() as session:
        states = BoatCrawlStateRepository(session)
        await states.record_success("u1")
        await states.record_success("u2")
        await states.record_failure("u3", "boom")
        status = await CrawlStatusRepository(session).get_status()

    assert status.boats_crawled == 2
    assert status.boats_failed == 1

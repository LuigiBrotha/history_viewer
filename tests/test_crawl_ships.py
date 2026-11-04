from datetime import date

import pytest

from app.crawl_ships import crawl_ships
from app.services.scraping.uboat_net.types import ShipHitRef
from app.services.storage.crawl_status_repository import CrawlStatusRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.ship_hit_repository import ShipHitRepository


async def _session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    return create_session_factory(engine)


def _refs(slug):
    return [
        ShipHitRef(str(n), slug, f"Ship {n}", date(1940, 7, n), 1000, "br", None, "sunk",
                   f"https://uboat.net/allies/merchants/ship/{n}.html")
        for n in (1, 2, 3)
    ]


class _Positions:
    """A position fetcher that records its calls; `plan` maps a ship page to a result or an exception."""

    def __init__(self, plan=None):
        self.calls = []
        self.plan = plan or {}

    def __call__(self, url):
        self.calls.append(url.rsplit("/", 1)[-1].removesuffix(".html"))
        result = self.plan.get(self.calls[-1], (50.0, -10.0))
        if isinstance(result, BaseException):
            raise result
        return result


async def _hits(session_factory):
    async with session_factory() as session:
        return await ShipHitRepository(session).list_hits()


async def test_crawl_stores_hits_and_their_positions(tmp_path):
    session_factory = await _session_factory(tmp_path)
    positions = _Positions({"2": None})

    await crawl_ships(["u99"], session_factory, _refs, positions)

    hits = await _hits(session_factory)
    assert [(h.ship_external_id, h.lat) for h in hits] == [("1", 50.0), ("2", None), ("3", 50.0)]


async def test_stopped_crawl_resumes_at_the_next_ship(tmp_path):
    session_factory = await _session_factory(tmp_path)

    with pytest.raises(KeyboardInterrupt):
        await crawl_ships(["u99"], session_factory, _refs, _Positions({"2": KeyboardInterrupt()}))
    assert len(await _hits(session_factory)) == 3  # visible before their positions are known

    resumed = _Positions()
    await crawl_ships(["u99"], session_factory, _refs, resumed)

    assert resumed.calls == ["2", "3"]


async def test_ship_without_a_position_is_not_retried_unless_forced(tmp_path):
    session_factory = await _session_factory(tmp_path)
    await crawl_ships(["u99"], session_factory, _refs, _Positions({"2": None}))

    again = _Positions()
    await crawl_ships(["u99"], session_factory, _refs, again)
    forced = _Positions()
    await crawl_ships(["u99"], session_factory, _refs, forced, force=True)

    assert again.calls == []
    assert forced.calls == ["1", "2", "3"]


async def test_failed_ship_is_retried_and_does_not_stop_the_crawl(tmp_path):
    session_factory = await _session_factory(tmp_path)
    first = _Positions({"2": RuntimeError("timeout")})
    await crawl_ships(["u99"], session_factory, _refs, first)

    assert first.calls == ["1", "2", "3"]
    retry = _Positions()
    await crawl_ships(["u99"], session_factory, _refs, retry)
    assert retry.calls == ["2"]


async def test_failed_boat_does_not_stop_the_next_boat(tmp_path):
    session_factory = await _session_factory(tmp_path)

    def successes(slug):
        if slug == "u1":
            raise RuntimeError("network error")
        return _refs(slug)

    await crawl_ships(["u1", "u2"], session_factory, successes, _Positions())

    assert {h.boat_slug for h in await _hits(session_factory)} == {"u2"}


async def test_limit_caps_the_positions_fetched_in_this_run(tmp_path):
    session_factory = await _session_factory(tmp_path)
    positions = _Positions()

    await crawl_ships(["u99"], session_factory, _refs, positions, limit=2)

    assert positions.calls == ["1", "2"]
    assert len(await _hits(session_factory)) == 3


async def test_status_revision_moves_when_a_ship_is_stored(tmp_path):
    session_factory = await _session_factory(tmp_path)
    async with session_factory() as session:
        before = (await CrawlStatusRepository(session).get_status()).revision

    await crawl_ships(["u99"], session_factory, _refs, _Positions())

    async with session_factory() as session:
        after = (await CrawlStatusRepository(session).get_status()).revision
    assert before is None
    assert after is not None

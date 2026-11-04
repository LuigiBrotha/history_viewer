import argparse
import asyncio

from app.core.config import settings
from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent
from app.services.scraping.uboat_net.ship import fetch_ship_position
from app.services.scraping.uboat_net.successes import fetch_successes
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.ship_hit_repository import ShipHitRepository


async def crawl_ships(slugs, session_factory, fetch_successes, fetch_ship_position, limit=None, force=False):
    """Store the ships hit by the given boats, then fetch the position of each hit that lacks one.

    Hits are stored as soon as the boat's list is read, so they are visible before their position
    is known. Each position is stored on its own: stopping loses at most the ship in flight. A
    failed request leaves the ship unchecked so the next run retries it; a page that loaded without
    a position counts as checked and is only fetched again with force. `limit` caps the positions
    fetched in this run.
    """
    stored = 0
    failed_boats = 0
    for i, slug in enumerate(slugs, start=1):
        print(f"[{i}/{len(slugs)}] {slug}")
        try:
            refs = await asyncio.to_thread(fetch_successes, slug)
            async with session_factory() as session:
                await ShipHitRepository(session).upsert_refs(refs)
            stored += len(refs)
        except Exception as exc:
            print(f"  FAILED {slug}: {exc}")
            failed_boats += 1

    async with session_factory() as session:
        pending = await ShipHitRepository(session).pending_positions(force=force, slugs=list(slugs))
    if limit is not None:
        pending = pending[:limit]

    found = unknown = failed = 0
    for i, hit in enumerate(pending, start=1):
        try:
            position = await asyncio.to_thread(fetch_ship_position, hit.detail_url)
            async with session_factory() as session:
                await ShipHitRepository(session).set_position(hit.id, position)
        except Exception as exc:
            print(f"  FAILED {hit.name} ({hit.boat_slug}): {exc}")
            failed += 1
            continue
        if position is None:
            unknown += 1
        else:
            found += 1
        print(f"[{i}/{len(pending)}] {hit.name} ({hit.boat_slug}): {'no position' if position is None else position}")

    print(
        f"{stored} hit(s) stored for {len(slugs) - failed_boats} boat(s), {failed_boats} boat(s) failed; "
        f"positions: {found} found, {unknown} unknown, {failed} failed."
    )


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Crawl uboat.net for the ships hit by U-boats and their positions.")
    parser.add_argument("--limit", type=int, default=None, help="Fetch the position of at most N ships in this run.")
    parser.add_argument("--slugs", type=str, default=None, help="Comma-separated boat slugs, e.g. u99,u100.")
    parser.add_argument("--force", action="store_true", help="Fetch positions again, also for ships without one.")
    parser.add_argument("--delay", type=float, default=None, help="Override CRAWL_DELAY_SECONDS.")
    return parser.parse_args(argv)


async def main(argv=None) -> None:
    args = _parse_args(argv)
    delay = args.delay if args.delay is not None else settings.CRAWL_DELAY_SECONDS

    engine = create_engine(settings.DATABASE_URL)
    await init_models(engine)
    session_factory = create_session_factory(engine)

    if args.slugs:
        slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
    else:
        async with session_factory() as session:
            slugs = [boat.slug for boat in await BoatRepository(session).list_summaries()]

    client = PoliteHttpClient(delay_seconds=delay, user_agent=build_user_agent(settings.CRAWLER_CONTACT))
    print(f"Crawling ships hit by {len(slugs)} boat(s) with a {delay}s delay between requests...")

    await crawl_ships(
        slugs,
        session_factory,
        fetch_successes=lambda slug: fetch_successes(client, slug),
        fetch_ship_position=lambda url: fetch_ship_position(client, url),
        limit=args.limit,
        force=args.force,
    )

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

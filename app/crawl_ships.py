import argparse
import asyncio

from sqlalchemy import func, select

from app.core.config import settings
from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent
from app.services.scraping.uboat_net.ship import fetch_ship_page
from app.services.scraping.uboat_net.successes import fetch_successes
from app.services.storage.models import Boat, Patrol
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.ship_detail_repository import ShipDetailRepository
from app.services.storage.ship_hit_repository import ShipHitRepository


async def crawl_ships(slugs, session_factory, fetch_successes, fetch_ship_page, limit=None, force=False, lists_only=False):
    """Store the ships hit by the given boats, then fetch the page of each hit that needs one.

    Hits are stored as soon as the boat's list is read, so they are visible before their position
    is known. A hit needs its page when its position is unchecked or its ship has no details yet.
    One request gives both; a ship hit more than once is fetched once per run. Each page is stored
    on its own: stopping loses at most the ship in flight. A failed request leaves the hit pending
    so the next run retries it; a page that loaded without a position counts as checked and is only
    fetched again with force. `limit` caps the pages fetched in this run. A boat's list is read once:
    a resumed run skips boats already listed, unless forced.
    """
    stored = 0
    failed_boats = 0
    listed = set()
    if not force:
        async with session_factory() as session:
            listed = await ShipHitRepository(session).listed_slugs()
    to_list = [slug for slug in slugs if slug not in listed]
    if len(to_list) < len(slugs):
        print(f"{len(slugs) - len(to_list)} boat list(s) already read, skipped.")
    for i, slug in enumerate(to_list, start=1):
        print(f"[{i}/{len(to_list)}] {slug}")
        try:
            refs = await asyncio.to_thread(fetch_successes, slug)
            async with session_factory() as session:
                repository = ShipHitRepository(session)
                await repository.upsert_refs(refs)
                await repository.mark_listed(slug)
            stored += len(refs)
        except Exception as exc:
            print(f"  FAILED {slug}: {exc}")
            failed_boats += 1

    if lists_only:
        print(f"{stored} hit(s) stored for {len(to_list) - failed_boats} boat(s), {failed_boats} failed.")
        return

    async with session_factory() as session:
        pending = await ShipHitRepository(session).pending_pages(force=force, slugs=list(slugs))

    found = unknown = failed = fetched = 0
    pages = {}  # ship_external_id -> (position, details), or None after a failure in this run
    for i, hit in enumerate(pending, start=1):
        label = f"[{i}/{len(pending)}] {hit.name} ({hit.boat_slug})"
        if hit.ship_external_id not in pages:
            if limit is not None and fetched >= limit:
                continue
            fetched += 1
            try:
                position, details = await asyncio.to_thread(fetch_ship_page, hit.detail_url)
                async with session_factory() as session:
                    await ShipDetailRepository(session).save(hit.ship_external_id, details)
            except Exception as exc:
                print(f"  FAILED {hit.name} ({hit.boat_slug}): {exc}")
                pages[hit.ship_external_id] = None
                failed += 1
                continue
            pages[hit.ship_external_id] = (position, details)
        elif pages[hit.ship_external_id] is None:
            continue
        position = pages[hit.ship_external_id][0]
        async with session_factory() as session:
            await ShipHitRepository(session).set_position(hit.id, position)
        if position is None:
            unknown += 1
        else:
            found += 1
        print(f"{label}: {'no position' if position is None else position}")

    print(
        f"{stored} hit(s) stored for {len(to_list) - failed_boats} boat(s), {failed_boats} boat(s) failed; "
        f"positions: {found} found, {unknown} unknown, {failed} failed."
    )


async def top_boats_by_tonnage(session_factory, count):
    """The boats with the most tonnage in their patrols, most first."""
    tonnage = func.sum(Patrol.tonnage)
    stmt = (
        select(Boat.slug)
        .join(Patrol, Patrol.boat_id == Boat.id)
        .group_by(Boat.id)
        .having(tonnage > 0)
        .order_by(tonnage.desc(), Boat.slug)
        .limit(count)
    )
    async with session_factory() as session:
        return list((await session.execute(stmt)).scalars())


async def boats_with_patrols(session_factory):
    """The boats that sailed at least one patrol, by slug: only they can have hit a ship."""
    stmt = select(Boat.slug).join(Patrol, Patrol.boat_id == Boat.id).distinct().order_by(Boat.slug)
    async with session_factory() as session:
        return list((await session.execute(stmt)).scalars())


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Crawl uboat.net for the ships hit by U-boats, their positions and details.")
    parser.add_argument("--limit", type=int, default=None, help="Fetch the page of at most N ships in this run.")
    parser.add_argument("--slugs", type=str, default=None, help="Comma-separated boat slugs, e.g. u99,u100.")
    parser.add_argument("--top-tonnage", type=int, default=None, help="Only the N boats with the most tonnage.")
    parser.add_argument("--lists-only", action="store_true", help="Read each boat's list of ships, no ship pages.")
    parser.add_argument("--force", action="store_true", help="Read every boat's list again and fetch every ship page again.")
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
    elif args.top_tonnage:
        slugs = await top_boats_by_tonnage(session_factory, args.top_tonnage)
    else:
        slugs = await boats_with_patrols(session_factory)

    client = PoliteHttpClient(delay_seconds=delay, user_agent=build_user_agent(settings.CRAWLER_CONTACT))
    print(f"Crawling ships hit by {len(slugs)} boat(s) with a {delay}s delay between requests...")

    await crawl_ships(
        slugs,
        session_factory,
        fetch_successes=lambda slug: fetch_successes(client, slug),
        fetch_ship_page=lambda url: fetch_ship_page(client, url),
        limit=args.limit,
        force=args.force,
        lists_only=args.lists_only,
    )

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

import argparse
import asyncio

from app.core.config import settings
from app.services.scraping.uboat_net.boat import fetch_boat
from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent
from app.services.scraping.uboat_net.listing import fetch_listing
from app.services.scraping.uboat_net.patrol_detail import fetch_patrol_detail
from app.services.scraping.uboat_net.patrol_list import fetch_patrol_list
from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.patrol_repository import PatrolRepository


async def crawl_boats(boat_refs, session_factory, fetch_boat, fetch_patrol_list, fetch_patrol_detail, force=False):
    for ref in boat_refs:
        if not force:
            async with session_factory() as session:
                existing = await BoatCrawlStateRepository(session).get(ref.slug)
            if existing is not None and existing.status == "success":
                continue

        try:
            boat_data = await asyncio.to_thread(fetch_boat, ref.slug)
            async with session_factory() as session:
                boat_repo = BoatRepository(session)
                await boat_repo.upsert_boat(boat_data)
                boat_id = await boat_repo.get_id_by_slug(ref.slug)

            summaries = await asyncio.to_thread(fetch_patrol_list, ref.slug)
            for summary in summaries:
                detail = await asyncio.to_thread(fetch_patrol_detail, summary.detail_url)
                async with session_factory() as session:
                    await PatrolRepository(session).upsert_patrol(boat_id, summary, detail)

            async with session_factory() as session:
                await BoatCrawlStateRepository(session).record_success(ref.slug)
        except Exception as exc:
            async with session_factory() as session:
                await BoatCrawlStateRepository(session).record_failure(ref.slug, str(exc))


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Crawl uboat.net for boats and patrol routes.")
    parser.add_argument("--limit", type=int, default=None, help="Crawl at most N boats from the listing.")
    parser.add_argument("--slugs", type=str, default=None, help="Comma-separated slugs to crawl, e.g. u99,u100.")
    parser.add_argument("--force", action="store_true", help="Re-crawl boats already marked successful.")
    parser.add_argument("--delay", type=float, default=None, help="Override CRAWL_DELAY_SECONDS.")
    return parser.parse_args(argv)


async def main(argv=None) -> None:
    args = _parse_args(argv)
    delay = args.delay if args.delay is not None else settings.CRAWL_DELAY_SECONDS

    engine = create_engine(settings.DATABASE_URL)
    await init_models(engine)
    session_factory = create_session_factory(engine)

    client = PoliteHttpClient(delay_seconds=delay, user_agent=build_user_agent(settings.CRAWLER_CONTACT))

    boat_refs = fetch_listing(client)
    if args.slugs:
        wanted = set(args.slugs.split(","))
        boat_refs = [ref for ref in boat_refs if ref.slug in wanted]
    if args.limit is not None:
        boat_refs = boat_refs[: args.limit]

    print(f"Crawling {len(boat_refs)} boat(s) with a {delay}s delay between requests...")

    await crawl_boats(
        boat_refs,
        session_factory,
        fetch_boat=lambda slug: fetch_boat(client, slug),
        fetch_patrol_list=lambda slug: fetch_patrol_list(client, slug),
        fetch_patrol_detail=lambda url: fetch_patrol_detail(client, url),
        force=args.force,
    )

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

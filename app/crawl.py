import argparse
import asyncio
import importlib

from app.compute_water_routes import compute_routes_for_points
from app.core.config import settings
from app.services.scraping.uboat_net.boat import fetch_boat
from app.services.scraping.uboat_net.http_client import PoliteHttpClient, build_user_agent
from app.services.scraping.uboat_net.listing import fetch_listing
from app.services.scraping.uboat_net.patrol_detail import fetch_patrol_detail
from app.services.scraping.uboat_net.patrol_list import fetch_patrol_list
from app.services.storage.boat_crawl_state_repository import BoatCrawlStateRepository
from app.services.storage.boat_repository import BoatRepository
from app.services.storage.crawl_status_repository import CrawlStatusRepository
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.patrol_repository import PatrolRepository


async def _boat_needs_crawl(slug, session_factory) -> bool:
    async with session_factory() as session:
        existing = await BoatCrawlStateRepository(session).get(slug)
    return existing is None or existing.status != "success"


async def select_boats_to_crawl(boat_refs, session_factory, limit=None, force=False):
    """Filter boat_refs down to those that still need crawling, then apply --limit.

    Applying --limit to the raw listing BEFORE the resumability skip would make
    `--limit N` silently re-select the same already-successful boats on a rerun
    (crawl_boats then skips all of them, issuing zero requests). Filtering first
    means `--limit N` always means "crawl up to N boats that still need it".

    With force=True, no boats are pre-filtered by status, so --limit applies to
    the same N boats from the listing every time, re-crawled regardless of prior
    status.
    """
    if force:
        selected = list(boat_refs)
    else:
        selected = [ref for ref in boat_refs if await _boat_needs_crawl(ref.slug, session_factory)]
    if limit is not None:
        selected = selected[:limit]
    return selected


async def crawl_boats(
    boat_refs, session_factory, fetch_boat, fetch_patrol_list, fetch_patrol_detail, force=False, route_leg=None
):
    succeeded = 0
    failed = 0
    total = len(boat_refs)
    for i, ref in enumerate(boat_refs, start=1):
        if not force:
            async with session_factory() as session:
                existing = await BoatCrawlStateRepository(session).get(ref.slug)
            if existing is not None and existing.status == "success":
                continue

        print(f"[{i}/{total}] {ref.slug}")
        try:
            boat_data = await asyncio.to_thread(fetch_boat, ref.slug)
            async with session_factory() as session:
                boat_repo = BoatRepository(session)
                await boat_repo.upsert_boat(boat_data)
                boat_id = await boat_repo.get_id_by_slug(ref.slug)

            summaries = await asyncio.to_thread(fetch_patrol_list, ref.slug)
            for summary in summaries:
                detail = await asyncio.to_thread(fetch_patrol_detail, summary.detail_url)
                if route_leg is not None:
                    await compute_routes_for_points(detail.route_points, session_factory, route_leg)
                async with session_factory() as session:
                    await PatrolRepository(session).upsert_patrol(boat_id, summary, detail)
                if route_leg is not None:
                    # Exclusions survive the re-crawl: the legs between the visible points may be new.
                    async with session_factory() as session:
                        visible = (await PatrolRepository(session).get_route(summary.external_id)).points
                    if await compute_routes_for_points(visible, session_factory, route_leg):
                        async with session_factory() as session:
                            await PatrolRepository(session).touch(summary.external_id)

            async with session_factory() as session:
                await BoatCrawlStateRepository(session).record_success(ref.slug)
            succeeded += 1
        except Exception as exc:
            async with session_factory() as session:
                await BoatCrawlStateRepository(session).record_failure(ref.slug, str(exc))
            print(f"  FAILED {ref.slug}: {exc}")
            failed += 1

    print(f"{succeeded} succeeded, {failed} failed.")


def load_route_leg():
    """Return the real route_leg, or None (crawl without routes) if its dependencies are missing."""
    try:
        # Imported lazily: pulls in numpy/shapely; land data loads on the first routed leg.
        water_router = importlib.import_module("app.routing_engine.water_router")
    except ImportError as exc:
        print(f"Routing unavailable ({exc}); crawling without water routes.")
        return None
    return water_router.route_leg


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
    async with session_factory() as session:
        await CrawlStatusRepository(session).set_listing_total(len(boat_refs))
    if args.slugs:
        wanted = set(args.slugs.split(","))
        boat_refs = [ref for ref in boat_refs if ref.slug in wanted]

    boat_refs = await select_boats_to_crawl(boat_refs, session_factory, limit=args.limit, force=args.force)

    print(f"Crawling {len(boat_refs)} boat(s) with a {delay}s delay between requests...")

    await crawl_boats(
        boat_refs,
        session_factory,
        fetch_boat=lambda slug: fetch_boat(client, slug),
        fetch_patrol_list=lambda slug: fetch_patrol_list(client, slug),
        fetch_patrol_detail=lambda url: fetch_patrol_detail(client, url),
        force=args.force,
        route_leg=load_route_leg(),
    )

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

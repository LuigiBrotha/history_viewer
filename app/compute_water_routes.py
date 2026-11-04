import argparse
import asyncio
import time
from collections import Counter

from sqlalchemy import select

from app.core.config import settings
from app.services.storage.database import create_engine, create_session_factory, init_models
from app.services.storage.models import Boat, Patrol, RoutePoint, WaterRoute
from app.services.storage.patrol_repository import PatrolRepository
from app.services.storage.water_route_repository import WaterRouteRepository


async def compute_routes_for_points(points, session_factory, route_leg, force=False, done=None) -> int:
    """Compute and store the legs between consecutive points that are not stored yet.

    A failing leg is printed and skipped; it never propagates to the caller.
    `done` is an optional set of pairs already handled in this run, so that with
    force=True a pair shared by several patrols is only recomputed once.
    Returns the number of legs computed.
    """
    coords = [(p.lat, p.lng) for p in points]
    pairs = list(zip(coords, coords[1:]))
    if done is not None:
        pairs = [pair for pair in pairs if pair not in done]
    try:
        async with session_factory() as session:
            todo = await WaterRouteRepository(session).missing(pairs, force=force)
    except Exception as exc:
        print(f"  ROUTES SKIPPED, could not read stored routes: {exc}")
        return 0

    computed = 0
    for start, end in todo:
        try:
            leg = await asyncio.to_thread(route_leg, start, end)
            async with session_factory() as session:
                await WaterRouteRepository(session).save(start, end, leg)
        except Exception as exc:
            print(f"  ROUTE FAILED {start} -> {end}: {exc}")
            continue
        if done is not None:
            done.add((start, end))
        computed += 1
    return computed


async def backfill(session_factory, route_leg, force=False) -> None:
    async with session_factory() as session:
        rows = (await session.execute(
            select(Patrol.id, Patrol.external_id, Boat.slug)
            .join(Boat, Patrol.boat_id == Boat.id)
            .order_by(Boat.slug, Patrol.patrol_number)
        )).all()

    total = len(rows)
    done: set = set()
    legs_computed = 0
    touched = 0
    started = time.monotonic()
    for i, (patrol_id, external_id, slug) in enumerate(rows, start=1):
        async with session_factory() as session:
            points = (await session.execute(
                select(RoutePoint).where(RoutePoint.patrol_id == patrol_id).order_by(RoutePoint.sequence)
            )).scalars().all()
        n = await compute_routes_for_points(points, session_factory, route_leg, force=force, done=done)
        print(f"[{i}/{total}] {slug} {external_id}: {n} legen berekend")
        if n:
            legs_computed += n
            async with session_factory() as session:
                await PatrolRepository(session).touch(external_id)
            touched += 1

    async with session_factory() as session:
        statuses = Counter((await session.execute(select(WaterRoute.status))).scalars().all())
    summary = ", ".join(f"{status}: {count}" for status, count in sorted(statuses.items())) or "geen"
    print(
        f"{legs_computed} legen berekend voor {touched} van {total} patrouilles "
        f"in {time.monotonic() - started:.1f}s. Opgeslagen routes per status: {summary}."
    )


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Compute water routes for already crawled patrols.")
    parser.add_argument("--force", action="store_true", help="Recompute legs that are already stored.")
    return parser.parse_args(argv)


async def main(argv=None) -> None:
    args = _parse_args(argv)
    from app.services.routing import water_router

    engine = create_engine(settings.DATABASE_URL)
    await init_models(engine)
    session_factory = create_session_factory(engine)
    await backfill(session_factory, water_router.route_leg, force=args.force)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

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


async def _read_points(session_factory, patrol_id):
    async with session_factory() as session:
        return (await session.execute(
            select(RoutePoint).where(RoutePoint.patrol_id == patrol_id).order_by(RoutePoint.sequence)
        )).scalars().all()


def consecutive_pairs(*point_lists):
    """Consecutive coordinate pairs of each list, without repeats, in order of first appearance."""
    pairs: dict = {}
    for points in point_lists:
        coords = [(p.lat, p.lng) for p in points]
        pairs.update(dict.fromkeys(zip(coords, coords[1:])))
    return list(pairs)


async def _read_visible_points(session_factory, external_id):
    async with session_factory() as session:
        return (await PatrolRepository(session).get_route(external_id)).points


async def compute_routes_for_points(
    points, session_factory, route_leg, force=False, done=None, failed=None, visible_points=None
) -> int:
    """Compute and store the legs between consecutive points that are not stored yet.

    `visible_points` are the points left after exclusions; their legs (A-C when B is
    excluded) are computed as well, next to those of the source `points`.

    A failing leg is printed and skipped; it never propagates to the caller.
    `done` is an optional set of pairs already handled in this run, so that with
    force=True a pair shared by several patrols is only recomputed once.
    `failed` is an optional list that collects the pairs that failed.
    Returns the number of legs computed.
    """
    pairs = consecutive_pairs(points, points if visible_points is None else visible_points)
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
            if failed is not None:
                failed.append((start, end))
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
    failed: list = []
    not_computed = 0
    started = time.monotonic()
    for i, (patrol_id, external_id, slug) in enumerate(rows, start=1):
        try:
            points = await _read_points(session_factory, patrol_id)
        except Exception as exc:
            print(f"[{i}/{total}] {slug} {external_id}: PATROL SKIPPED, could not read points: {exc}")
            continue
        try:
            visible = await _read_visible_points(session_factory, external_id)
        except Exception as exc:
            print(f"  VISIBLE POINTS UNREADABLE for {external_id}, using the source rows only: {exc}")
            visible = points
        pairs = consecutive_pairs(points, visible)
        n = await compute_routes_for_points(
            points, session_factory, route_leg, force=force, done=done, failed=failed, visible_points=visible
        )
        print(f"[{i}/{total}] {slug} {external_id}: {n} legen berekend")
        legs_computed += n
        try:
            async with session_factory() as session:
                stored = await WaterRouteRepository(session).get_many(pairs)
            not_computed += sum(1 for pair in pairs if pair not in stored)
        except Exception as exc:
            print(f"  COUNT SKIPPED, could not read stored routes: {exc}")
        # A pair computed for an earlier patrol also changes this patrol's legs.
        if n or any(pair in done for pair in pairs):
            try:
                async with session_factory() as session:
                    await PatrolRepository(session).touch(external_id)
                touched += 1
            except Exception as exc:
                print(f"  TOUCH FAILED {external_id}: {exc}")

    async with session_factory() as session:
        statuses = Counter((await session.execute(select(WaterRoute.status))).scalars().all())
    summary = ", ".join(f"{status}: {count}" for status, count in sorted(statuses.items())) or "geen"
    print(
        f"{legs_computed} legen berekend voor {touched} van {total} patrouilles "
        f"in {time.monotonic() - started:.1f}s. Opgeslagen routes per status: {summary}. "
        f"{len(failed)} legen mislukt, {not_computed} legen nog niet berekend."
    )


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Compute water routes for already crawled patrols.")
    parser.add_argument("--force", action="store_true", help="Recompute legs that are already stored.")
    return parser.parse_args(argv)


async def main(argv=None) -> None:
    args = _parse_args(argv)
    from app.routing_engine import water_router

    engine = create_engine(settings.DATABASE_URL)
    await init_models(engine)
    session_factory = create_session_factory(engine)
    await backfill(session_factory, water_router.route_leg, force=args.force)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

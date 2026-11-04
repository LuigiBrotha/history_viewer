from app.services.export.uboats import LegOut, RoutePointOut
from app.services.routing.types import RoutedLeg

MAX_KM_PER_DAY = 815

ON_LAND_REASON = "Route onzeker: punt ligt op land"
NO_ROUTE_REASON = "Route onzeker: geen waterroute gevonden"


def _suspect_reason(length_km: float, days: int) -> str:
    unit = "dag" if days == 1 else "dagen"
    return f"Verdacht: {round(length_km)} km in {days} {unit}"


def build_legs(
    points: list[RoutePointOut],
    routes: dict[tuple[tuple[float, float], tuple[float, float]], RoutedLeg],
) -> list[LegOut]:
    legs = []
    for start, end in zip(points, points[1:]):
        days = (end.date - start.date).days if start.date and end.date else None
        stored = routes.get(((start.lat, start.lng), (end.lat, end.lng)))
        status, reason, path, length_km = "not_computed", None, None, None
        if stored is not None:
            status = stored.status
            path = [[lat, lng] for lat, lng in stored.path] if stored.path else None
            length_km = stored.length_km
            if status == "on_land":
                reason = ON_LAND_REASON
            elif status == "no_route":
                reason = NO_ROUTE_REASON
            elif (
                status == "ok"
                and days is not None
                and length_km is not None
                and length_km > MAX_KM_PER_DAY * max(1, days)
            ):
                status = "suspect"
                reason = _suspect_reason(length_km, days)
        legs.append(LegOut(
            from_sequence=start.sequence,
            to_sequence=end.sequence,
            status=status,
            reason=reason,
            path=path,
            length_km=length_km,
            days=days,
        ))
    return legs

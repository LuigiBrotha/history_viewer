from dataclasses import replace
from datetime import date, timedelta

from app.services.export.uboats import RoutePointOut


def with_approximate_dates(
    points: list[RoutePointOut],
    departure: date | None,
    arrival: date | None,
) -> list[RoutePointOut]:
    """Spread undated points evenly between departure and arrival, marked as approximate.

    The source often lists more positions than dates without saying which belongs to
    which. A patrol with any known date is left alone, and so is one that lacks a
    departure or arrival: nothing is guessed without both ends.
    """
    if departure is None or arrival is None or any(point.date is not None for point in points):
        return points

    days = (arrival - departure).days
    steps = max(1, len(points) - 1)
    return [
        replace(point, date=departure + timedelta(days=round(i * days / steps)), date_approximate=True)
        for i, point in enumerate(points)
    ]

from datetime import date

from app.services.export.uboats import RoutePointOut
from app.services.routing.approximate_dates import with_approximate_dates


def _points(*dates):
    return [RoutePointOut(sequence=i, lat=float(i), lng=float(i), date=d) for i, d in enumerate(dates)]


def test_spreads_undated_points_evenly_from_departure_to_arrival():
    result = with_approximate_dates(_points(None, None, None), date(1940, 1, 1), date(1940, 1, 11))

    assert [p.date for p in result] == [date(1940, 1, 1), date(1940, 1, 6), date(1940, 1, 11)]
    assert all(p.date_approximate for p in result)


def test_more_points_than_days_share_dates():
    result = with_approximate_dates(_points(None, None, None, None), date(1940, 1, 1), date(1940, 1, 2))

    assert result[0].date == date(1940, 1, 1)
    assert result[-1].date == date(1940, 1, 2)
    assert [p.date for p in result] == sorted(p.date for p in result)


def test_a_single_point_gets_the_departure_date():
    result = with_approximate_dates(_points(None), date(1940, 1, 1), date(1940, 1, 11))

    assert [p.date for p in result] == [date(1940, 1, 1)]
    assert result[0].date_approximate


def test_a_patrol_with_a_known_date_is_left_alone():
    points = _points(date(1940, 1, 3), None)

    assert with_approximate_dates(points, date(1940, 1, 1), date(1940, 1, 11)) == points


def test_without_departure_or_arrival_nothing_is_guessed():
    points = _points(None, None)

    assert with_approximate_dates(points, None, date(1940, 1, 11)) == points
    assert with_approximate_dates(points, date(1940, 1, 1), None) == points
    assert not any(p.date_approximate for p in points)


def test_keeps_sequence_and_coordinates():
    result = with_approximate_dates(_points(None, None), date(1940, 1, 1), date(1940, 1, 2))

    assert [(p.sequence, p.lat, p.lng) for p in result] == [(0, 0.0, 0.0), (1, 1.0, 1.0)]

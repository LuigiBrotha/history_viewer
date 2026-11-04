from datetime import date

from app.services.export.uboats import RoutePointOut
from app.services.routing.legs import MAX_KM_PER_DAY, build_legs
from app.services.routing.types import RoutedLeg

A = (50.0, -5.0)
B = (51.0, -4.0)


def _points(d1=date(1940, 6, 1), d2=date(1940, 6, 2)):
    return [RoutePointOut(1, *A, d1), RoutePointOut(2, *B, d2)]


def _leg(km, d1=date(1940, 6, 1), d2=date(1940, 6, 2)):
    routes = {(A, B): RoutedLeg("ok", [A, B], km)}
    return build_legs(_points(d1, d2), routes)[0]


def test_limit_constant():
    assert MAX_KM_PER_DAY == 815


def test_ok_leg_at_exactly_the_limit_is_not_suspect():
    leg = _leg(815)
    assert leg.status == "ok" and leg.reason is None and leg.days == 1
    assert leg.path == [[50.0, -5.0], [51.0, -4.0]]
    assert (leg.from_sequence, leg.to_sequence, leg.length_km) == (1, 2, 815)


def test_leg_over_the_limit_is_suspect():
    leg = _leg(816)
    assert leg.status == "suspect"
    assert leg.reason == "Verdacht: 816 km in 1 dag"


def test_same_date_uses_a_minimum_of_one_day():
    leg = _leg(816, date(1940, 6, 1), date(1940, 6, 1))
    assert leg.status == "suspect" and leg.days == 0
    assert leg.reason == "Verdacht: 816 km in 0 dagen"


def test_limit_scales_with_days():
    assert _leg(1600, d2=date(1940, 6, 3)).status == "ok"
    assert _leg(1631, d2=date(1940, 6, 3)).reason == "Verdacht: 1631 km in 2 dagen"


def test_undated_point_is_never_suspect():
    leg = _leg(5000, d2=None)
    assert leg.status == "ok" and leg.days is None


def test_on_land_leg_has_the_dutch_reason():
    leg = build_legs(_points(), {(A, B): RoutedLeg("on_land", None, None)})[0]
    assert leg.status == "on_land"
    assert leg.reason == "Route onzeker: punt ligt op land"
    assert leg.path is None


def test_no_route_leg_has_the_dutch_reason():
    leg = build_legs(_points(), {(A, B): RoutedLeg("no_route", None, None)})[0]
    assert leg.reason == "Route onzeker: geen waterroute gevonden"


def test_missing_stored_route_is_not_computed():
    leg = build_legs(_points(), {})[0]
    assert leg.status == "not_computed" and leg.reason is None and leg.path is None


def test_fewer_than_two_points_has_no_legs():
    assert build_legs(_points()[:1], {}) == []


def test_interior_vertices_are_rounded_to_six_decimals_and_ends_stay_exact():
    start, end = (50.123456789, -5.987654321), (51.000000049, -4.5)
    path = [start, (50.5555555555, -4.1234567891), (50.7, -4.3000004), end]
    points = [RoutePointOut(1, *start, date(1940, 6, 1)), RoutePointOut(2, *end, date(1940, 6, 2))]

    leg = build_legs(points, {(start, end): RoutedLeg("ok", path, 100.0)})[0]

    assert leg.path == [
        [50.123456789, -5.987654321],
        [50.555556, -4.123457],
        [50.7, -4.3],
        [51.000000049, -4.5],
    ]


def test_two_vertex_path_is_left_untouched():
    start, end = (50.123456789, -5.987654321), (51.000000049, -4.5)
    points = [RoutePointOut(1, *start, date(1940, 6, 1)), RoutePointOut(2, *end, date(1940, 6, 2))]

    leg = build_legs(points, {(start, end): RoutedLeg("ok", [start, end], 100.0)})[0]

    assert leg.path == [list(start), list(end)]


def test_out_of_order_dates_use_the_absolute_number_of_days():
    leg = _leg(816, date(1940, 6, 4), date(1940, 6, 1))
    assert leg.days == -3
    assert leg.status == "ok"
    leg = _leg(2446, date(1940, 6, 4), date(1940, 6, 1))
    assert leg.status == "suspect"
    assert leg.reason == "Verdacht: 2446 km in 3 dagen"

import math

import pytest

from app.services.routing.land import Land, load_land
from app.services.routing.water_router import RoutedLeg, route_leg

LORIENT = (47.85, -3.25)
BAY_OF_BISCAY = (46.95, -9.25)
CASPIAN_SEA = (42.0, 50.5)
NORTH_SEA = (56.0, 3.0)
KIEL = (54.3667, 10.1667)
BRUNSBUETTEL = (53.9, 9.1333)
BERGEN = (61.35, 3.8667)
GRID_CELL_AT_KIEL_BERGEN = 0.05  # the first attempt's cell size is at most this


@pytest.fixture(scope="module")
def land() -> Land:
    return load_land()


def _km(a, b) -> float:
    p = math.radians
    h = (
        math.sin(p(b[0] - a[0]) / 2) ** 2
        + math.cos(p(a[0])) * math.cos(p(b[0])) * math.sin(p(b[1] - a[1]) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(h))


def test_open_sea_leg_is_a_straight_two_point_path(land):
    leg = route_leg((50.0, -20.0), (52.0, -25.0), land)
    assert leg.status == "ok"
    assert leg.path == [(50.0, -20.0), (52.0, -25.0)]
    assert leg.length_km == pytest.approx(_km((50.0, -20.0), (52.0, -25.0)))


def test_path_starts_and_ends_on_the_original_coordinates(land):
    leg = route_leg(LORIENT, BAY_OF_BISCAY, land)
    assert leg.path[0] == LORIENT and leg.path[-1] == BAY_OF_BISCAY


def test_length_is_measured_on_the_stored_path(land):
    leg = route_leg(LORIENT, BAY_OF_BISCAY, land)
    expected = sum(_km(a, b) for a, b in zip(leg.path, leg.path[1:]))
    assert leg.length_km == pytest.approx(expected)


def test_lorient_reaches_open_sea(land):
    assert route_leg(LORIENT, BAY_OF_BISCAY, land).status == "ok"


def test_kiel_to_brunsbuettel_uses_the_canal(land):
    leg = route_leg(KIEL, BRUNSBUETTEL, land)
    assert leg.status == "ok" and leg.length_km < 150


def test_kiel_to_bergen_stays_off_jutland(land):
    leg = route_leg(KIEL, BERGEN, land)
    assert leg.status == "ok" and 900 < leg.length_km < 1200


def test_point_deep_inland_is_on_land(land):
    leg = route_leg((76.65, -26.5), (74.85, 15.5), land)
    assert leg == RoutedLeg(status="on_land", path=None, length_km=None)


def test_point_just_inland_is_snapped_and_routed(land):
    # LORIENT lies about 7.4 km inland.
    leg = route_leg(LORIENT, BAY_OF_BISCAY, land)
    assert leg.status == "ok" and len(leg.path) > 2


def test_interior_segments_stay_within_one_cell_of_water(land):
    from shapely.geometry import LineString

    leg = route_leg(KIEL, BERGEN, land)
    interior = leg.path[1:-1]
    for a, b in zip(interior, interior[1:]):
        line = LineString([(a[1], a[0]), (b[1], b[0])])
        clipped = line.intersection(land.geometry)
        assert clipped.length <= GRID_CELL_AT_KIEL_BERGEN


def test_landlocked_water_has_no_route(land):
    leg = route_leg(CASPIAN_SEA, NORTH_SEA, land)
    assert leg == RoutedLeg(status="no_route", path=None, length_km=None)


def test_route_leg_loads_land_itself_when_none_given():
    assert route_leg((50.0, -20.0), (52.0, -25.0)).status == "ok"

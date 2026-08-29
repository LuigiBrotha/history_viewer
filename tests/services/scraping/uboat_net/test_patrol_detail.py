from datetime import date
from pathlib import Path

from app.services.scraping.uboat_net.patrol_detail import parse_patrol_detail

_FIXTURE = Path(__file__).parent.parent.parent.parent / "fixtures" / "uboat_net" / "patrol_4754.html"


def test_parse_patrol_detail_extracts_all_route_points_from_real_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")

    detail = parse_patrol_detail(html)

    assert len(detail.route_points) == 11
    assert detail.route_points[0].sequence == 0
    assert detail.route_points[0].lat == 54.3667
    assert detail.route_points[0].lng == 10.1667
    assert detail.route_points[-1].lat == 53.5167
    assert detail.route_points[-1].lng == 8.15


def test_parse_patrol_detail_zips_dates_onto_route_points_in_order():
    html = _FIXTURE.read_text(encoding="utf-8")

    detail = parse_patrol_detail(html)

    assert detail.route_points[0].date == date(1940, 6, 18)
    assert detail.route_points[6].date == date(1940, 6, 24)
    assert detail.route_points[7].date == date(1940, 6, 25)
    assert detail.route_points[-1].date == date(1940, 6, 25)


def test_parse_patrol_detail_extracts_description():
    html = _FIXTURE.read_text(encoding="utf-8")

    detail = parse_patrol_detail(html)

    assert detail.description is not None
    assert "Left Germany for a patrol" in detail.description


def test_parse_patrol_detail_missing_route_script_returns_empty_points():
    detail = parse_patrol_detail("<div class='emphasis'><p>No map on this page.</p></div>")

    assert detail.route_points == []
    assert detail.description == "No map on this page."


def test_parse_patrol_detail_more_coordinates_than_dates_leaves_extra_points_undated():
    html = """
    <script>var patrolRouteCoordinates = [[1.0, 2.0],[3.0, 4.0]];</script>
    <a href="/boats/patrols/u1/1940-01-01.html">1 Jan 1940</a>
    """

    detail = parse_patrol_detail(html)

    assert len(detail.route_points) == 2
    assert detail.route_points[0].date == date(1940, 1, 1)
    assert detail.route_points[1].date is None

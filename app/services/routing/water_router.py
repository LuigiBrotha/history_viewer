import heapq
import math
from dataclasses import dataclass

import numpy as np
import shapely
from scipy import ndimage
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

from app.services.routing.land import Land, load_land
from app.services.routing.types import LatLng, RoutedLeg

EARTH_RADIUS_KM = 6371.0
KM_PER_DEGREE = 111.0
SNAP_MAX_KM = 10.0
SNAP_OFFSHORE_DEGREES = 0.002
SNAP_BOX_FACTOR = 1.5
MIN_COS_LATITUDE = 0.01
ENDPOINT_MAX_KM = 10.0
DISPLAY_LINE_INTERVALS = 16
MAX_LATITUDE = 85.0
MAX_WINDOW_CELLS = 4_000_000

# (cell divisor, min cell, max cell, min margin, margin factor), in degrees
ATTEMPTS = (
    (300, 0.005, 0.05, 0.3, 0.3),
    (600, 0.005, 0.05, 1.0, 0.8),
    (400, 0.01, 0.05, 4.0, 2.0),
)

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
FOUR_CONNECTED = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]


@dataclass(frozen=True)
class Window:
    lat0: float
    lng0: float
    cell: float
    rows: int
    cols: int

    def lat(self, row: float) -> float:
        return self.lat0 + row * self.cell

    def lng(self, col: float) -> float:
        return self.lng0 + col * self.cell

    def to_latlng(self, node: tuple[int, int]) -> LatLng:
        return (self.lat(node[0]), self.lng(node[1]))


def haversine_km(a: LatLng, b: LatLng) -> float:
    dlat = math.radians(b[0] - a[0])
    dlng = math.radians(b[1] - a[1])
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlng / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(h))


def path_length_km(path: list[LatLng]) -> float:
    return sum(haversine_km(a, b) for a, b in zip(path, path[1:]))


def _mercator_y(lat: float) -> float:
    lat = max(-MAX_LATITUDE, min(MAX_LATITUDE, lat))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _inverse_mercator_y(y: float) -> float:
    return math.degrees(2 * math.atan(math.exp(y)) - math.pi / 2)


def display_line(a: LatLng, b: LatLng) -> LineString:
    """The line Leaflet draws between a and b: straight in Web Mercator."""
    ya, yb = _mercator_y(a[0]), _mercator_y(b[0])
    n = DISPLAY_LINE_INTERVALS
    return LineString(
        [
            (a[1] + (b[1] - a[1]) * i / n, _inverse_mercator_y(ya + (yb - ya) * i / n))
            for i in range(n + 1)
        ]
    )


def is_clear(land: Land, a: LatLng, b: LatLng) -> bool:
    return not land.geometry.intersects(display_line(a, b))


def _nearest_coast(land: Land, point: LatLng) -> LatLng | None:
    """Nearest coast point within SNAP_MAX_KM, measured in locally cos(lat)-scaled degrees."""
    cos_lat = max(math.cos(math.radians(point[0])), MIN_COS_LATITUDE)
    half_lat = SNAP_MAX_KM / KM_PER_DEGREE * SNAP_BOX_FACTOR
    half_lng = half_lat / cos_lat
    west, east = point[1] - half_lng, point[1] + half_lng
    south, north = point[0] - half_lat, point[0] + half_lat
    near = shapely.clip_by_rect(land.boundary, west, south, east, north)
    if near.is_empty:
        return None
    scaled = shapely.transform(near, lambda xy: xy * [cos_lat, 1.0])
    nearest = nearest_points(scaled, Point(point[1] * cos_lat, point[0]))[0]
    coast = (nearest.y, nearest.x / cos_lat)
    return coast if haversine_km(point, coast) <= SNAP_MAX_KM else None


def snap_offshore(land: Land, point: LatLng) -> LatLng | None:
    """Move a point on land just offshore; None when it is too far inland."""
    if not land.geometry.contains(Point(point[1], point[0])):
        return point
    coast = _nearest_coast(land, point)
    if coast is None:
        return None
    cos_lat = max(math.cos(math.radians(point[0])), MIN_COS_LATITUDE)
    dx, dy = (coast[1] - point[1]) * cos_lat, coast[0] - point[0]
    length = math.hypot(dx, dy) or 1.0
    return (
        coast[0] + dy / length * SNAP_OFFSHORE_DEGREES,
        coast[1] + dx / length * SNAP_OFFSHORE_DEGREES / cos_lat,
    )


def pull_string(land: Land, points: list[LatLng]) -> list[LatLng]:
    """From each vertex, jump to the furthest later vertex with a clear display line."""
    out = [points[0]]
    i = 0
    while i < len(points) - 1:
        j = len(points) - 1
        while j > i + 1 and not is_clear(land, points[i], points[j]):
            j -= 1
        out.append(points[j])
        i = j
    return out


def make_window(
    a: LatLng, b: LatLng, cell: float, margin: float, capped: bool = False
) -> Window:
    lat0 = max(min(a[0], b[0]) - margin, -MAX_LATITUDE)
    lat1 = min(max(a[0], b[0]) + margin, MAX_LATITUDE)
    lng0 = min(a[1], b[1]) - margin
    lng1 = max(a[1], b[1]) + margin
    height, width = lat1 - lat0, lng1 - lng0
    if capped:
        cell = max(cell, math.sqrt(height * width / MAX_WINDOW_CELLS))
    return Window(lat0, lng0, cell, int(height / cell) + 1, int(width / cell) + 1)


def rasterize_water(land: Land, window: Window) -> np.ndarray:
    lngs, lats = np.meshgrid(
        window.lng0 + np.arange(window.cols) * window.cell,
        window.lat0 + np.arange(window.rows) * window.cell,
    )
    return ~shapely.contains_xy(land.geometry, lngs, lats)


def pick_endpoint(
    window: Window, water: np.ndarray, labels: np.ndarray, sizes: np.ndarray, point: LatLng
) -> tuple[int, int] | None:
    """Nearest water cell within range that lies in the largest region reachable within range."""
    row = round((point[0] - window.lat0) / window.cell)
    col = round((point[1] - window.lng0) / window.cell)
    cos_lat = max(math.cos(math.radians(point[0])), 0.1)
    reach = int(ENDPOINT_MAX_KM / (KM_PER_DEGREE * window.cell) / cos_lat) + 1
    r0, r1 = max(row - reach, 0), min(row + reach + 1, window.rows)
    c0, c1 = max(col - reach, 0), min(col + reach + 1, window.cols)
    near = [
        (r0 + int(i), c0 + int(j))
        for i, j in np.argwhere(water[r0:r1, c0:c1])
        if haversine_km(point, window.to_latlng((r0 + int(i), c0 + int(j)))) <= ENDPOINT_MAX_KM
    ]
    if not near:
        return None
    largest = max(sizes[labels[node]] for node in near)
    in_largest = [node for node in near if sizes[labels[node]] == largest]
    return min(in_largest, key=lambda n: (n[0] - row) ** 2 + ((n[1] - col) * cos_lat) ** 2)


def search(
    window: Window, water: np.ndarray, start: tuple[int, int], goal: tuple[int, int]
) -> list[tuple[int, int]]:
    """A* over water cells, 8 neighbours, longitude scaled by cos(latitude), no corner cutting."""
    top_lat = min(MAX_LATITUDE, max(abs(window.lat(0)), abs(window.lat(window.rows - 1))))
    min_cos = math.cos(math.radians(top_lat))

    def heuristic(n):
        return math.hypot(n[0] - goal[0], (n[1] - goal[1]) * min_cos)

    best = {start: 0.0}
    prev: dict[tuple[int, int], tuple[int, int]] = {}
    queue = [(heuristic(start), start)]
    while queue:
        f, node = heapq.heappop(queue)
        if node == goal:
            break
        if f > best[node] + heuristic(node) + 1e-9:
            continue
        cos_lat = math.cos(math.radians(window.lat(node[0])))
        for dr, dc in NEIGHBOURS:
            r, c = node[0] + dr, node[1] + dc
            if not (0 <= r < window.rows and 0 <= c < window.cols) or not water[r, c]:
                continue
            if dr and dc and not (water[node[0] + dr, node[1]] and water[node[0], node[1] + dc]):
                continue
            cost = best[node] + math.hypot(dr, dc * cos_lat)
            if cost < best.get((r, c), math.inf):
                best[(r, c)] = cost
                prev[(r, c)] = node
                heapq.heappush(queue, (cost + heuristic((r, c)), (r, c)))
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    return path[::-1]


def grid_route(
    land: Land, a: LatLng, b: LatLng, cell: float, margin: float, capped: bool
) -> list[LatLng] | None:
    window = make_window(a, b, cell, margin, capped)
    water = rasterize_water(land, window)
    labels, _ = ndimage.label(water, structure=FOUR_CONNECTED)
    sizes = np.bincount(labels.ravel())
    start = pick_endpoint(window, water, labels, sizes, a)
    goal = pick_endpoint(window, water, labels, sizes, b)
    if start is None or goal is None or labels[start] != labels[goal]:
        return None
    return [window.to_latlng(node) for node in search(window, water, start, goal)]


def attempt_parameters(extent: float):
    for divisor, min_cell, max_cell, min_margin, margin_factor in ATTEMPTS:
        cell = max(min_cell, min(max_cell, extent / divisor))
        yield cell, max(min_margin, extent * margin_factor)


def _finish(path: list[LatLng]) -> RoutedLeg:
    return RoutedLeg(status="ok", path=path, length_km=path_length_km(path))


def route_leg(start: LatLng, end: LatLng, land: Land | None = None) -> RoutedLeg:
    land = land or load_land()
    snapped_start, snapped_end = snap_offshore(land, start), snap_offshore(land, end)
    if snapped_start is None or snapped_end is None:
        return RoutedLeg(status="on_land", path=None, length_km=None)
    if is_clear(land, snapped_start, snapped_end):
        return _finish([start, end])
    extent = max(abs(start[0] - end[0]), abs(start[1] - end[1]))
    for number, (cell, margin) in enumerate(attempt_parameters(extent), start=1):
        grid = grid_route(land, snapped_start, snapped_end, cell, margin, number == len(ATTEMPTS))
        if grid is not None:
            pulled = pull_string(land, [snapped_start, *grid, snapped_end])
            return _finish([start, *pulled[1:-1], end])
    return RoutedLeg(status="no_route", path=None, length_km=None)

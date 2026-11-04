import gzip
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import shapely
from shapely.geometry import LineString, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

DATA_DIR = Path(__file__).parent / "data"
LAND_FILES = ("ne_10m_land.geojson.gz", "ne_10m_minor_islands.geojson.gz")

# Kiel Canal as (lng, lat) vertices, cut out of the land as water.
KIEL_CANAL_LINE = [
    (9.13, 53.885),
    (9.27, 54.0),
    (9.53, 54.2),
    (9.68, 54.30),
    (9.85, 54.34),
    (10.02, 54.36),
    (10.15, 54.368),
]
KIEL_CANAL_BUFFER_DEGREES = 0.015


@dataclass(frozen=True)
class Land:
    geometry: BaseGeometry
    boundary: BaseGeometry


def _read_geometries(path: Path) -> list[BaseGeometry]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    return [shape(feature["geometry"]).buffer(0) for feature in features]


def _cut_kiel_canal(land: BaseGeometry) -> BaseGeometry:
    canal = LineString(KIEL_CANAL_LINE).buffer(KIEL_CANAL_BUFFER_DEGREES)
    return land.difference(canal)


def build_land(paths: list[Path]) -> Land:
    geometries = [g for path in paths for g in _read_geometries(path)]
    geometry = _cut_kiel_canal(unary_union(geometries))
    shapely.prepare(geometry)
    return Land(geometry=geometry, boundary=geometry.boundary)


@lru_cache(maxsize=1)
def load_land() -> Land:
    return build_land([DATA_DIR / name for name in LAND_FILES])

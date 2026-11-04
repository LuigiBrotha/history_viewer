from dataclasses import dataclass
from typing import Literal

LatLng = tuple[float, float]


@dataclass(frozen=True)
class RoutedLeg:
    status: Literal["ok", "on_land", "no_route"]
    path: list[LatLng] | None
    length_km: float | None

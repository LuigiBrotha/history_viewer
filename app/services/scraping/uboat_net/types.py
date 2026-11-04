from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class BoatRef:
    slug: str
    number: str


@dataclass(frozen=True)
class BoatData:
    slug: str
    number: str
    type: str | None
    builder: str | None
    laid_down: date | None
    launched: date | None
    commissioned: date | None
    fate: str | None


@dataclass(frozen=True)
class RoutePointData:
    sequence: int
    lat: float
    lng: float
    date: date | None


@dataclass(frozen=True)
class PatrolSummary:
    external_id: str
    patrol_number: int
    commander: str | None
    departure_port: str | None
    departure_date: date | None
    arrival_port: str | None
    arrival_date: date | None
    days_at_sea: int | None
    tonnage: int | None
    detail_url: str


@dataclass(frozen=True)
class PatrolDetail:
    description: str | None
    route_points: list[RoutePointData] = field(default_factory=list)


@dataclass(frozen=True)
class ShipHitRef:
    ship_external_id: str
    boat_slug: str
    name: str
    date: date
    tons: int
    nationality: str | None
    convoy: str | None
    outcome: Literal["sunk", "damaged", "captured"]
    detail_url: str

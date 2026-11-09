from dataclasses import dataclass, field
from datetime import date, datetime

from app.services.scraping.uboat_net.types import ShipDetails


@dataclass(frozen=True)
class BoatSummary:
    slug: str
    number: str
    type: str | None
    fate: str | None
    patrol_count: int
    tonnage: int = 0


@dataclass(frozen=True)
class PatrolSummaryOut:
    external_id: str
    patrol_number: int
    commander: str | None
    departure_port: str | None
    departure_date: date | None
    arrival_port: str | None
    arrival_date: date | None
    days_at_sea: int | None
    tonnage: int | None
    description: str | None = None


@dataclass(frozen=True)
class BoatDetail:
    slug: str
    number: str
    type: str | None
    builder: str | None
    laid_down: date | None
    launched: date | None
    commissioned: date | None
    fate: str | None
    patrols: list[PatrolSummaryOut] = field(default_factory=list)
    # Whether the running text is the Dutch version.
    translated: bool = False


@dataclass(frozen=True)
class RoutePointOut:
    sequence: int
    lat: float
    lng: float
    date: date | None
    date_approximate: bool = False


@dataclass(frozen=True)
class LegOut:
    from_sequence: int
    to_sequence: int
    status: str
    reason: str | None
    path: list[list[float]] | None
    length_km: float | None
    days: int | None


@dataclass(frozen=True)
class PatrolRouteOut:
    boat_slug: str
    boat_number: str
    external_id: str
    departure_date: date | None
    arrival_date: date | None
    patrol_number: int = 0
    points: list[RoutePointOut] = field(default_factory=list)
    legs: list[LegOut] = field(default_factory=list)
    excluded_points: list[RoutePointOut] = field(default_factory=list)


@dataclass(frozen=True)
class LastPatrolOut:
    boat_slug: str
    boat_number: str
    external_id: str
    crawled_at: datetime


@dataclass(frozen=True)
class CrawlStatusOut:
    listing_total: int | None
    boats_crawled: int
    boats_failed: int
    patrol_count: int
    revision: datetime | None
    last_patrol: LastPatrolOut | None
    can_edit: bool = False


@dataclass(frozen=True)
class PatrolPeriodOut:
    departure_date: date
    arrival_date: date


@dataclass(frozen=True)
class ShipHitOut:
    ship_external_id: str
    boat_slug: str
    boat_number: str
    name: str
    date: date
    tons: int
    nationality: str | None
    convoy: str | None
    outcome: str
    lat: float | None
    lng: float | None
    updated_at: datetime


@dataclass(frozen=True)
class ShipDetailOut:
    ship_external_id: str
    details: ShipDetails | None
    hits: list[ShipHitOut] = field(default_factory=list)
    # Whether the running text is the Dutch version.
    translated: bool = False

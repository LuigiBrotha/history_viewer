from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores naive UTC datetimes but always returns timezone-aware UTC datetimes.

    SQLite (via aiosqlite) silently discards tzinfo on write and returns naive
    datetimes on read, regardless of whether the column is declared with
    DateTime(timezone=True). This TypeDecorator makes that limitation
    transparent to consumers of the ORM.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Boat(Base):
    __tablename__ = "boats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    number: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str | None] = mapped_column(String, nullable=True)
    builder: Mapped[str | None] = mapped_column(String, nullable=True)
    laid_down: Mapped[date | None] = mapped_column(Date, nullable=True)
    launched: Mapped[date | None] = mapped_column(Date, nullable=True)
    commissioned: Mapped[date | None] = mapped_column(Date, nullable=True)
    fate: Mapped[str | None] = mapped_column(String, nullable=True)

    patrols: Mapped[list["Patrol"]] = relationship(back_populates="boat", cascade="all, delete-orphan")


class Patrol(Base):
    __tablename__ = "patrols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boat_id: Mapped[int] = mapped_column(ForeignKey("boats.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    patrol_number: Mapped[int] = mapped_column(Integer, nullable=False)
    commander: Mapped[str | None] = mapped_column(String, nullable=True)
    departure_port: Mapped[str | None] = mapped_column(String, nullable=True)
    departure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    arrival_port: Mapped[str | None] = mapped_column(String, nullable=True)
    arrival_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_at_sea: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tonnage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    crawled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    boat: Mapped["Boat"] = relationship(back_populates="patrols")
    route_points: Mapped[list["RoutePoint"]] = relationship(back_populates="patrol", cascade="all, delete-orphan")


class RoutePoint(Base):
    __tablename__ = "route_points"
    __table_args__ = (UniqueConstraint("patrol_id", "sequence", name="uq_route_points_patrol_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patrol_id: Mapped[int] = mapped_column(ForeignKey("patrols.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)

    patrol: Mapped["Patrol"] = relationship(back_populates="route_points")


class BoatCrawlState(Base):
    __tablename__ = "boat_crawl_state"

    slug: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)


class CrawlProgress(Base):
    __tablename__ = "crawl_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_total: Mapped[int] = mapped_column(Integer, nullable=False)


class WaterRoute(Base):
    __tablename__ = "water_routes"

    from_lat: Mapped[float] = mapped_column(Float, primary_key=True)
    from_lng: Mapped[float] = mapped_column(Float, primary_key=True)
    to_lat: Mapped[float] = mapped_column(Float, primary_key=True)
    to_lng: Mapped[float] = mapped_column(Float, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    length_km: Mapped[float | None] = mapped_column(Float, nullable=True)


class ShipHit(Base):
    __tablename__ = "ship_hits"
    __table_args__ = (
        UniqueConstraint("ship_external_id", "boat_slug", "date", name="uq_ship_hits_ship_boat_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ship_external_id: Mapped[str] = mapped_column(String, nullable=False)
    boat_slug: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tons: Mapped[int] = mapped_column(Integer, nullable=False)
    nationality: Mapped[str | None] = mapped_column(String, nullable=True)
    convoy: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    detail_url: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class ExcludedRoutePoint(Base):
    """A route point a user hid. Keyed on content, not sequence, so it survives a re-crawl."""

    __tablename__ = "excluded_route_points"

    external_id: Mapped[str] = mapped_column(String, primary_key=True)
    lat: Mapped[float] = mapped_column(Float, primary_key=True)
    lng: Mapped[float] = mapped_column(Float, primary_key=True)
    # ISO date, or an empty string for a missing date (a primary key column cannot be NULL).
    date: Mapped[str] = mapped_column(String, primary_key=True)

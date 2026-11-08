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
    """A route point a user hid. Keyed on position, not sequence or date, so it survives a re-crawl.

    `occurrence` is the 0-based ordinal, by sequence, among the patrol's rows with the same
    coordinates, so a twin elsewhere on the route stays visible."""

    __tablename__ = "excluded_route_points"

    external_id: Mapped[str] = mapped_column(String, primary_key=True)
    lat: Mapped[float] = mapped_column(Float, primary_key=True)
    lng: Mapped[float] = mapped_column(Float, primary_key=True)
    occurrence: Mapped[int] = mapped_column(Integer, primary_key=True)


class ShipDetail(Base):
    """What a ship's own page says, once per ship however often it was hit."""

    __tablename__ = "ship_details"

    ship_external_id: Mapped[str] = mapped_column(String, primary_key=True)
    ship_type: Mapped[str | None] = mapped_column(String, nullable=True)
    completed: Mapped[str | None] = mapped_column(String, nullable=True)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    homeport: Mapped[str | None] = mapped_column(String, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String, nullable=True)
    fate: Mapped[str | None] = mapped_column(String, nullable=True)
    complement: Mapped[str | None] = mapped_column(String, nullable=True)
    convoy: Mapped[str | None] = mapped_column(String, nullable=True)
    route: Mapped[str | None] = mapped_column(String, nullable=True)
    cargo: Mapped[str | None] = mapped_column(String, nullable=True)
    history: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BattlePosition(Base):
    """Where the user hand-placed a Veldslag on the map, keyed on its title in battles.json."""

    __tablename__ = "battle_positions"

    title: Mapped[str] = mapped_column(String, primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BattleArticle(Base):
    """The wikitext of a World War II battle article, exactly as in the Wikipedia dump."""

    __tablename__ = "battle_articles"

    title: Mapped[str] = mapped_column(String, primary_key=True)
    wikitext: Mapped[str] = mapped_column(Text, nullable=False)
    dump_name: Mapped[str] = mapped_column(String, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BattleRedirect(Base):
    """A Wikipedia redirect whose target is a stored battle article."""

    __tablename__ = "battle_redirects"

    alias: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, ForeignKey("battle_articles.title"), nullable=False)


class ShipListState(Base):
    """A boat whose list of ships hit has been read, so a resumed crawl can skip it."""

    __tablename__ = "ship_list_state"

    boat_slug: Mapped[str] = mapped_column(String, primary_key=True)
    listed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class PlaceSearch(Base):
    """A place search answer kept for ever, keyed on its source and the lowercased, trimmed query. An empty list is an answer too."""

    __tablename__ = "place_searches"

    query: Mapped[str] = mapped_column(String, primary_key=True)
    results_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class ForeignBattleArticle(Base):
    """The wikitext of a battle article in another language than English, as in that dump."""

    __tablename__ = "foreign_battle_articles"

    lang: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, primary_key=True)
    # The Veldslag this article belongs to: an English title, or its own for a new Veldslag.
    battle: Mapped[str | None] = mapped_column(String, nullable=True)
    wikitext: Mapped[str] = mapped_column(Text, nullable=False)
    dump_name: Mapped[str] = mapped_column(String, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class BattleHints(Base):
    """The Plaatshints of a Veldslag: the places its articles name, as a JSON list of
    {"name", "lat", "lng", "kind"} ("infobox" or "artikel"). Written by tools.place_hints."""

    __tablename__ = "battle_hints"

    battle: Mapped[str] = mapped_column(String, primary_key=True)
    hints_json: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class DutchArticle(Base):
    """The Dutch version of an Artikel (its language and title): the article of the Dutch
    Wikipedia about the same battle ("wikipedia", its wikitext), else a machine translation of the
    rendered original ("vertaald", its HTML). Written by tools.dutch_articles and when asked."""

    __tablename__ = "dutch_articles"

    lang: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    nl_title: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    made_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

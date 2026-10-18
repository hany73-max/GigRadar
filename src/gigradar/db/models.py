"""SQLAlchemy 2.x declarative models for GigRadar database."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    # Use standard JSON compatible across SQLite and PostgreSQL with SQL NULL representation
    type_annotation_map = {
        dict[str, Any]: JSON(none_as_null=True),
        list[str]: JSON(none_as_null=True),
        list[dict[str, Any]]: JSON(none_as_null=True),
    }


def utc_now() -> datetime:
    """Return current timestamp in UTC timezone."""
    return datetime.now(UTC)


class Platform(Base):
    """Registered platform being monitored (e.g. Mostaql, Khamsat, Freelancer)."""

    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Relationships
    gigs: Mapped[list["Gig"]] = relationship(
        "Gig", back_populates="platform", cascade="all, delete-orphan"
    )
    scrape_runs: Mapped[list["ScrapeRun"]] = relationship(
        "ScrapeRun", back_populates="platform", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Platform(id={self.id}, name='{self.name}', is_paused={self.is_paused})>"


class Gig(Base):
    """Stored freelancing gig / project."""

    __tablename__ = "gigs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    budget_min_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_max_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_usd_est: Mapped[float | None] = mapped_column(Float, nullable=True)
    project_type: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed")
    bids_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deadline_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_stats_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    category_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags_raw_json: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_html_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail_level: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    detail_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    processing_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="new", index=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )

    __table_args__ = (
        UniqueConstraint("platform_id", "external_id", name="uq_gigs_platform_external_id"),
    )

    # Relationships
    platform: Mapped["Platform"] = relationship("Platform", back_populates="gigs")
    snapshots: Mapped[list["GigSnapshot"]] = relationship(
        "GigSnapshot",
        back_populates="gig",
        cascade="all, delete-orphan",
        order_by="GigSnapshot.seen_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Gig(id={self.id}, platform_id={self.platform_id}, "
            f"external_id='{self.external_id}', state='{self.processing_state}')>"
        )


class GigSnapshot(Base):
    """Snapshot recording changes to bid count over time for a gig."""

    __tablename__ = "gig_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gig_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gigs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bids_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    # Relationships
    gig: Mapped["Gig"] = relationship("Gig", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<GigSnapshot(id={self.id}, gig_id={self.gig_id}, bids_count={self.bids_count})>"


class ScrapeRun(Base):
    """Log record of a scraping or polling execution tick."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gigs_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gigs_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    # Relationships
    platform: Mapped["Platform"] = relationship("Platform", back_populates="scrape_runs")

    def __repr__(self) -> str:
        return (
            f"<ScrapeRun(id={self.id}, platform_id={self.platform_id}, "
            f"found={self.gigs_found}, new={self.gigs_new})>"
        )

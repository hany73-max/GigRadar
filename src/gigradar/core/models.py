"""Core domain models for GigRadar."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class GigStub(BaseModel):
    """Lightweight representation of a gig discovered from a listing page."""

    platform_id: str
    external_id: str
    url: str
    title: str
    posted_at: datetime | None = None
    bids_count: int | None = None
    brief_description: str | None = None
    client_name: str | None = None
    detail_level: Literal["full", "title_only"] = "full"


class Gig(BaseModel):
    """Full representation of a scraped or fetched project/request."""

    platform_id: str
    external_id: str
    url: str
    title: str
    description: str
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str = "USD"
    budget_min_usd: float | None = None
    budget_max_usd: float | None = None
    budget_usd_est: float | None = None
    bids_count: int | None = None
    posted_at: datetime | None = None
    deadline_text: str | None = None
    client_name: str | None = None
    client_stats: dict[str, Any] = Field(default_factory=dict)
    category_raw: str | None = None
    tags_raw: list[str] = Field(default_factory=list)
    language: Literal["ar", "en", "mixed"] = "ar"
    project_type: Literal["fixed", "hourly"] = "fixed"
    detail_level: Literal["full", "title_only"] = "full"
    raw_html_hash: str | None = None


class HealthReport(BaseModel):
    """Health check outcome for layout drift detection."""

    platform_id: str
    is_healthy: bool
    message: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

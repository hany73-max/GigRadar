"""Pydantic validation models for GigRadar YAML configurations."""

from pydantic import BaseModel, ConfigDict, Field


class ConfigBaseModel(BaseModel):
    """Base class for all YAML configuration models, strictly forbidding unknown keys."""

    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------------------------
class ProjectItem(ConfigBaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    one_liner: str


class PortfolioConfig(ConfigBaseModel):
    projects: list[ProjectItem] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Owner Profile
# ------------------------------------------------------------------------------
class LanguageSkill(ConfigBaseModel):
    language: str
    proficiency: str


class OwnerInfo(ConfigBaseModel):
    name: str
    title: str
    location: str
    seniority: str
    education: str
    languages: list[LanguageSkill] = Field(default_factory=list)


class SkillTier(ConfigBaseModel):
    description: str
    skills: list[str] = Field(default_factory=list)


class SkillTiers(ConfigBaseModel):
    tier_a: SkillTier
    tier_b: SkillTier
    tier_c: SkillTier


class ProfileConfig(ConfigBaseModel):
    owner: OwnerInfo
    skill_tiers: SkillTiers
    hard_rejects: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Claims Allowlist
# ------------------------------------------------------------------------------
class ClaimsAllowlistConfig(ConfigBaseModel):
    allowed_claims: dict[str, list[str]] = Field(default_factory=dict)
    forbidden_patterns: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Stage 1 Rules
# ------------------------------------------------------------------------------
class RulesThresholds(ConfigBaseModel):
    min_budget_usd: float = 25.0
    min_hourly_rate_usd: float = 15.0
    max_existing_bids: int = 30
    max_gig_age_minutes: int = 1440


class KeywordFamily(ConfigBaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)


class CategoryRules(ConfigBaseModel):
    deny_categories: list[str] = Field(default_factory=list)
    allow_categories: list[str] = Field(default_factory=list)


class RulesConfig(ConfigBaseModel):
    thresholds: RulesThresholds = Field(default_factory=RulesThresholds)
    keyword_families: dict[str, KeywordFamily] = Field(default_factory=dict)
    ambiguous_keywords: dict[str, str] = Field(default_factory=dict)
    exclude_keywords: list[str] = Field(default_factory=list)
    hard_rejects: dict[str, list[str]] = Field(default_factory=dict)
    category_rules: CategoryRules = Field(default_factory=CategoryRules)


# ------------------------------------------------------------------------------
# Platforms
# ------------------------------------------------------------------------------
class PlatformThresholds(ConfigBaseModel):
    max_existing_bids: int | None = None
    min_budget_usd: float | None = None
    max_gig_age_minutes: int | None = None
    min_expected_listing_rows: int = 5


class PlatformSettings(ConfigBaseModel):
    name: str
    enabled: bool = True
    type: str  # "scraper" or "api"
    base_url: str
    listing_url: str | None = None
    base_api_url: str | None = None
    poll_interval_seconds: int = 120
    jitter_seconds_min: int = 5
    jitter_seconds_max: int = 20
    max_pages_per_run: int = 2
    timeout_seconds: int = 30
    user_agent: str = "GigRadar/0.1.0"
    max_bid_length_chars: int | None = None
    skill_ids: list[int] | None = None
    circuit_breaker_failures: int = 3
    circuit_breaker_cooldown_minutes: int = 15
    thresholds: PlatformThresholds = Field(default_factory=PlatformThresholds)


class PlatformsConfig(ConfigBaseModel):
    platforms: dict[str, PlatformSettings] = Field(default_factory=dict)


# ------------------------------------------------------------------------------
# Resolved Thresholds
# ------------------------------------------------------------------------------
class ResolvedThresholds(ConfigBaseModel):
    max_existing_bids: int
    min_budget_usd: float
    min_hourly_rate_usd: float = 15.0
    max_gig_age_minutes: int
    min_expected_listing_rows: int

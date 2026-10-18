"""Pydantic validation models for GigRadar YAML configurations."""

from pydantic import BaseModel, Field


# ------------------------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------------------------
class ProjectItem(BaseModel):
    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    one_liner: str


class PortfolioConfig(BaseModel):
    projects: list[ProjectItem] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Owner Profile
# ------------------------------------------------------------------------------
class LanguageSkill(BaseModel):
    language: str
    proficiency: str


class OwnerInfo(BaseModel):
    name: str
    title: str
    location: str
    seniority: str
    education: str
    languages: list[LanguageSkill] = Field(default_factory=list)


class SkillTier(BaseModel):
    description: str
    skills: list[str] = Field(default_factory=list)


class SkillTiers(BaseModel):
    tier_a: SkillTier
    tier_b: SkillTier
    tier_c: SkillTier


class ProfileConfig(BaseModel):
    owner: OwnerInfo
    skill_tiers: SkillTiers
    hard_rejects: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Claims Allowlist
# ------------------------------------------------------------------------------
class ClaimsAllowlistConfig(BaseModel):
    allowed_claims: dict[str, list[str]] = Field(default_factory=dict)
    forbidden_patterns: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Stage 1 Rules
# ------------------------------------------------------------------------------
class RulesThresholds(BaseModel):
    min_budget_usd: float = 25.0
    max_existing_bids: int = 30
    max_gig_age_minutes: int = 1440


class KeywordFamily(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)


class CategoryRules(BaseModel):
    deny_categories: list[str] = Field(default_factory=list)
    allow_categories: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    thresholds: RulesThresholds = Field(default_factory=RulesThresholds)
    keyword_families: dict[str, KeywordFamily] = Field(default_factory=dict)
    hard_rejects: dict[str, list[str]] = Field(default_factory=dict)
    category_rules: CategoryRules = Field(default_factory=CategoryRules)


# ------------------------------------------------------------------------------
# Platforms
# ------------------------------------------------------------------------------
class PlatformThresholds(BaseModel):
    max_existing_bids: int = 30
    min_budget_usd: float = 25.0
    max_gig_age_minutes: int = 1440


class PlatformSettings(BaseModel):
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


class PlatformsConfig(BaseModel):
    platforms: dict[str, PlatformSettings] = Field(default_factory=dict)

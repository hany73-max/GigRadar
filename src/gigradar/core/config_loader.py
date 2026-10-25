"""Loaders and validators for YAML configuration files."""

from pathlib import Path
from typing import Any

import yaml

from gigradar.core.config_models import (
    ClaimsAllowlistConfig,
    PlatformsConfig,
    PortfolioConfig,
    ProfileConfig,
    ResolvedThresholds,
    RulesConfig,
)
from gigradar.core.settings import get_settings


def _get_config_dir(config_dir: Path | None = None) -> Path:
    if config_dir is not None:
        return config_dir
    import os

    env_dir = os.environ.get("GIGRADAR_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return get_settings().config_dir


def load_yaml(file_path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML content in {file_path} must be a dictionary/mapping")
    return data


def load_portfolio_config(config_dir: Path | None = None) -> PortfolioConfig:
    """Load and validate portfolio.yaml."""
    base = _get_config_dir(config_dir)
    raw = load_yaml(base / "portfolio.yaml")
    return PortfolioConfig.model_validate(raw)


def load_profile_config(config_dir: Path | None = None) -> ProfileConfig:
    """Load and validate profile.yaml."""
    base = _get_config_dir(config_dir)
    raw = load_yaml(base / "profile.yaml")
    return ProfileConfig.model_validate(raw)


def load_claims_allowlist_config(config_dir: Path | None = None) -> ClaimsAllowlistConfig:
    """Load and validate claims_allowlist.yaml."""
    base = _get_config_dir(config_dir)
    raw = load_yaml(base / "claims_allowlist.yaml")
    return ClaimsAllowlistConfig.model_validate(raw)


def load_rules_config(config_dir: Path | None = None) -> RulesConfig:
    """Load and validate rules.yaml."""
    base = _get_config_dir(config_dir)
    raw = load_yaml(base / "rules.yaml")
    return RulesConfig.model_validate(raw)


def load_platforms_config(config_dir: Path | None = None) -> PlatformsConfig:
    """Load and validate platforms.yaml."""
    base = _get_config_dir(config_dir)
    raw = load_yaml(base / "platforms.yaml")
    return PlatformsConfig.model_validate(raw)


def resolve_platform_thresholds(
    platform_name: str, config_dir: Path | None = None
) -> ResolvedThresholds:
    """Resolve platform thresholds by inheriting unset values (None) from rules.yaml.

    Only 'platform not in config' falls back to rules.yaml defaults.
    Any YAML syntax or validation error in config files propagates.
    """
    rules_cfg = load_rules_config(config_dir)
    default_bids = rules_cfg.thresholds.max_existing_bids
    default_budget = rules_cfg.thresholds.min_budget_usd
    default_hourly = rules_cfg.thresholds.min_hourly_rate_usd
    default_age = rules_cfg.thresholds.max_gig_age_minutes
    default_min_rows = 5

    platforms_cfg = load_platforms_config(config_dir)
    norm_name = platform_name.strip().lower()
    plat = platforms_cfg.platforms.get(norm_name)
    if plat is not None:
        pt = plat.thresholds
        return ResolvedThresholds(
            max_existing_bids=pt.max_existing_bids
            if pt.max_existing_bids is not None
            else default_bids,
            min_budget_usd=pt.min_budget_usd if pt.min_budget_usd is not None else default_budget,
            min_hourly_rate_usd=default_hourly,
            max_gig_age_minutes=pt.max_gig_age_minutes
            if pt.max_gig_age_minutes is not None
            else default_age,
            min_expected_listing_rows=pt.min_expected_listing_rows
            if pt.min_expected_listing_rows is not None
            else default_min_rows,
        )

    return ResolvedThresholds(
        max_existing_bids=default_bids,
        min_budget_usd=default_budget,
        min_hourly_rate_usd=default_hourly,
        max_gig_age_minutes=default_age,
        min_expected_listing_rows=default_min_rows,
    )


def validate_all_configs(config_dir: Path | None = None) -> dict[str, str]:
    """Validate all 5 YAML configurations and return status per file."""
    results: dict[str, str] = {}
    base = _get_config_dir(config_dir)

    loaders = [
        ("portfolio.yaml", load_portfolio_config),
        ("profile.yaml", load_profile_config),
        ("claims_allowlist.yaml", load_claims_allowlist_config),
        ("rules.yaml", load_rules_config),
        ("platforms.yaml", load_platforms_config),
    ]

    for filename, loader in loaders:
        file_path = base / filename
        if not file_path.exists():
            results[filename] = f"MISSING ({file_path})"
            continue
        try:
            loader(base)
            results[filename] = "OK"
        except Exception as exc:  # noqa: BLE001
            results[filename] = f"INVALID ({exc})"

    return results

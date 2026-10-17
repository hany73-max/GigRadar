"""Loaders and validators for YAML configuration files."""

from pathlib import Path
from typing import Any

import yaml

from gigradar.core.config_models import (
    ClaimsAllowlistConfig,
    PlatformsConfig,
    PortfolioConfig,
    ProfileConfig,
    RulesConfig,
)
from gigradar.core.settings import get_settings


def _get_config_dir(config_dir: Path | None = None) -> Path:
    if config_dir is not None:
        return config_dir
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

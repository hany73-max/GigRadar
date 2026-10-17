"""Tests for YAML configuration loading and Pydantic validation."""

from pathlib import Path

from gigradar.core.config_loader import (
    load_claims_allowlist_config,
    load_platforms_config,
    load_portfolio_config,
    load_profile_config,
    load_rules_config,
    validate_all_configs,
)

CONFIG_DIR = Path("config")


def test_load_portfolio_config() -> None:
    config = load_portfolio_config(CONFIG_DIR)
    assert len(config.projects) >= 5
    ids = [p.id for p in config.projects]
    assert "sky_spy" in ids
    assert "kessler_shield" in ids
    assert "ticketsense" in ids
    assert "ml_blueprint" in ids
    assert "fmcw_radar" in ids


def test_load_profile_config() -> None:
    config = load_profile_config(CONFIG_DIR)
    assert config.owner.name == "Hany Elashry"
    assert config.owner.seniority == "Junior"
    assert len(config.skill_tiers.tier_a.skills) > 0
    assert len(config.skill_tiers.tier_b.skills) > 0
    assert len(config.skill_tiers.tier_c.skills) > 0
    assert len(config.hard_rejects) > 0


def test_load_claims_allowlist_config() -> None:
    config = load_claims_allowlist_config(CONFIG_DIR)
    assert "tabular_ml" in config.allowed_claims
    assert "deep_learning" in config.allowed_claims
    assert len(config.forbidden_patterns) > 0


def test_load_rules_config() -> None:
    config = load_rules_config(CONFIG_DIR)
    assert config.thresholds.min_budget_usd >= 25.0
    assert "ml_dl" in config.keyword_families
    assert "academic" in config.hard_rejects
    assert "Design & Graphics" in config.category_rules.deny_categories


def test_load_platforms_config() -> None:
    config = load_platforms_config(CONFIG_DIR)
    assert "mostaql" in config.platforms
    assert "khamsat" in config.platforms
    assert "freelancer" in config.platforms
    assert config.platforms["mostaql"].enabled is True
    assert config.platforms["freelancer"].type == "api"


def test_validate_all_configs() -> None:
    results = validate_all_configs(CONFIG_DIR)
    assert len(results) == 5
    for file, status in results.items():
        assert status == "OK", f"Config {file} failed validation: {status}"


def test_validate_missing_dir(tmp_path: Path) -> None:
    results = validate_all_configs(tmp_path)
    assert len(results) == 5
    for _file, status in results.items():
        assert "MISSING" in status

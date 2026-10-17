"""Tests for Typer CLI commands."""

import pytest
from typer.testing import CliRunner

import gigradar.core.settings as settings_module
from gigradar.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "GigRadar version" in result.stdout


def test_cli_doctor_skip_llm() -> None:
    result = runner.invoke(app, ["doctor", "--skip-live-llm"])
    assert result.exit_code == 0
    assert "GigRadar Doctor" in result.stdout
    assert "portfolio.yaml" in result.stdout
    assert "rules.yaml" in result.stdout


def test_cli_doctor_detects_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    # Reset cached settings so env overrides are loaded
    monkeypatch.setattr(settings_module, "_settings", None)
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "123456789")

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "PLACEHOLDER" in result.stdout
    assert "Configured" not in result.stdout
    assert "your_gemini_api_key_here" in result.stdout

    # Clean up cached settings
    monkeypatch.setattr(settings_module, "_settings", None)

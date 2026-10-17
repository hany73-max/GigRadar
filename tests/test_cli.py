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


def test_cli_scrape_once_unsupported_platform() -> None:
    result = runner.invoke(app, ["scrape-once", "unknown_platform"])
    assert result.exit_code == 1
    assert "Unsupported platform" in result.stdout


def test_cli_scrape_once_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    import gigradar.cli as cli_module
    from gigradar.core.models import Gig

    sample_gig = Gig(
        platform_id="mostaql",
        external_id="123456",
        url="https://mostaql.com/project/123456",
        title="بناء نموذج تعلم آلي",
        description="تفاصيل المشروع",
        budget_min=100.0,
        budget_max=250.0,
        currency="USD",
        bids_count=5,
        posted_at=None,
        client_name="Test Client",
        language="ar",
    )

    async def mock_run_scrape_once(platform_name: str, limit: int, fetch_details: bool) -> list[Gig]:
        return [sample_gig]

    monkeypatch.setattr(cli_module, "_run_scrape_once", mock_run_scrape_once)

    result = runner.invoke(app, ["scrape-once", "mostaql", "--limit", "1"])
    assert result.exit_code == 0
    assert "123456" in result.stdout
    assert "Mostaql" in result.stdout
    assert "$100 - $250" in result.stdout

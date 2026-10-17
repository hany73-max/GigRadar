"""Tests for Typer CLI commands."""

from typer.testing import CliRunner

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

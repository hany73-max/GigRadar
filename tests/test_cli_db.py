"""Tests for CLI database and run commands: db upgrade, db stats, run --once, and doctor DB checks."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from gigradar.cli import app
from gigradar.pipeline.orchestrator import TickResult

runner = CliRunner()


def test_cli_db_upgrade_and_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "cli_test.db"
    db_url = f"sqlite+aiosqlite:///{test_db.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # 1. db upgrade
    res_up = runner.invoke(app, ["db", "upgrade"])
    assert res_up.exit_code == 0
    assert "Database upgrade successful!" in res_up.stdout

    # 2. db stats
    res_stats = runner.invoke(app, ["db", "stats"])
    assert res_stats.exit_code == 0
    assert "Storage Summary" in res_stats.stdout
    assert "Total Stored Gigs" in res_stats.stdout


def test_cli_doctor_db_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "doctor_test.db"
    db_url = f"sqlite+aiosqlite:///{test_db.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # Doctor before upgrade -> pending
    res1 = runner.invoke(app, ["doctor", "--offline"])
    assert "Database & Migrations" in res1.stdout
    assert "PENDING" in res1.stdout

    # Upgrade
    res_up = runner.invoke(app, ["db", "upgrade"])
    assert res_up.exit_code == 0

    # Doctor after upgrade -> up to date
    res2 = runner.invoke(app, ["doctor", "--offline"])
    assert "UP TO DATE" in res2.stdout


def test_cli_run_once(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_run_once = AsyncMock(
        return_value={
            "mostaql": TickResult(platform="mostaql", gigs_found=5, gigs_new=2, success=True),
            "khamsat": TickResult(platform="khamsat", gigs_found=3, gigs_new=1, success=True),
            "freelancer": TickResult(
                platform="freelancer", gigs_found=10, gigs_new=4, success=True
            ),
        }
    )

    with patch("gigradar.pipeline.scheduler.SchedulerRunner.run_once", mock_run_once):
        res = runner.invoke(app, ["run", "--once"])
        assert res.exit_code == 0
        assert "Polling Tick Summary" in res.stdout
        assert "mostaql" in res.stdout
        assert "khamsat" in res.stdout
        assert "freelancer" in res.stdout

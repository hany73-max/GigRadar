"""Tests for Alembic migrations: upgrade to head, downgrade to base, upgrade again."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Validate that Alembic migrations run cleanly up to head and down to base on SQLite."""
    test_db = tmp_path / "migration_test.db"
    db_url = f"sqlite+aiosqlite:///{test_db.as_posix()}"

    # Prepare Alembic Config pointing to the temporary database
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    # Verify tables exist
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "alembic_version" in tables
    assert "platforms" in tables
    assert "gigs" in tables
    assert "gig_snapshots" in tables
    assert "scrape_runs" in tables

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    # Verify tables were dropped
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_after_down = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "platforms" not in tables_after_down
    assert "gigs" not in tables_after_down
    assert "gig_snapshots" not in tables_after_down
    assert "scrape_runs" not in tables_after_down

    # 3. Upgrade to head again
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_reupgrade = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "platforms" in tables_reupgrade
    assert "gigs" in tables_reupgrade

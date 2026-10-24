"""Global pytest configuration and isolation fixtures for GigRadar."""

import shutil
from collections.abc import Generator
from pathlib import Path
from typing import NamedTuple

import pytest
from sqlalchemy import create_engine

from gigradar.core.settings import reload_settings
from gigradar.db.models import Base
from gigradar.db.session import reset_global_engine

REAL_DB_PATH = Path("gigradar.db").resolve()


class DbStat(NamedTuple):
    exists: bool
    size: int
    mtime_ns: int


def get_real_db_stat() -> DbStat:
    """Capture presence and file modification stats of gigradar.db."""
    if REAL_DB_PATH.exists():
        stat = REAL_DB_PATH.stat()
        return DbStat(exists=True, size=stat.st_size, mtime_ns=stat.st_mtime_ns)
    return DbStat(exists=False, size=0, mtime_ns=0)


# Session-level initial stat captured at import time
INITIAL_REAL_DB_STAT = get_real_db_stat()


@pytest.fixture(scope="session", autouse=True)
def guard_real_database() -> Generator[DbStat, None, None]:
    """Record gigradar.db presence and stats at session start and assert unchanged at end."""
    initial = INITIAL_REAL_DB_STAT
    yield initial
    final = get_real_db_stat()
    assert final == initial, (
        f"Real database ({REAL_DB_PATH}) was modified during test run! "
        f"Before: {initial}, After: {final}"
    )


@pytest.fixture(scope="session")
def template_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a single template SQLite database with all tables created via Base.metadata."""
    temp_dir = tmp_path_factory.mktemp("db_template")
    template_path = temp_dir / "template.db"
    sync_engine = create_engine(f"sqlite:///{template_path.as_posix()}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    return template_path


@pytest.fixture(autouse=True)
def isolate_database_and_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_db_path: Path,
) -> Generator[None, None, None]:
    """Autouse fixture providing per-test DB isolation and resetting settings/engine."""
    test_db = tmp_path / "test_isolated.db"
    shutil.copyfile(template_db_path, test_db)
    test_db_url = f"sqlite+aiosqlite:///{test_db.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", test_db_url)
    reload_settings()
    reset_global_engine()

    yield

    reset_global_engine()
    reload_settings()

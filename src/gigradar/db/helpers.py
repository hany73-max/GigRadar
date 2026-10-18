"""Database maintenance and migration helper utilities."""

from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from gigradar.db.session import get_async_session

logger = structlog.get_logger(__name__)


def get_alembic_config(
    config_path: str = "alembic.ini",
    database_url: str | None = None,
) -> Config:
    """Load Alembic Config pointing to alembic.ini."""
    ini_path = Path(config_path)
    if not ini_path.exists():
        # Fallback to repo root if called from elsewhere
        ini_path = Path(__file__).resolve().parent.parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    if database_url:
        from gigradar.db.session import normalize_async_database_url

        cfg.set_main_option("sqlalchemy.url", normalize_async_database_url(database_url))
    return cfg


def run_db_upgrade(revision: str = "head", database_url: str | None = None) -> None:
    """Run Alembic migrations up to specified revision (default 'head')."""
    alembic_cfg = get_alembic_config(database_url=database_url)
    command.upgrade(alembic_cfg, revision)


def run_db_downgrade(revision: str = "base", database_url: str | None = None) -> None:
    """Run Alembic migrations down to specified revision (default 'base')."""
    alembic_cfg = get_alembic_config(database_url=database_url)
    command.downgrade(alembic_cfg, revision)


async def check_db_connectivity_and_version(
    database_url: str | None = None,
) -> tuple[bool, str, str | None, str | None]:
    """Test database connectivity and verify current migration vs alembic head revision.

    Returns:
        (is_healthy, status_message, current_revision, head_revision)
    """
    from gigradar.db.session import create_engine_from_url

    alembic_cfg = get_alembic_config(database_url=database_url)
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    engine = create_engine_from_url(database_url) if database_url else None
    current_rev: str | None = None
    try:
        async with get_async_session(engine=engine) as session:
            # 1. Test basic connectivity
            await session.execute(text("SELECT 1"))

            # 2. Check alembic_version table
            try:
                result = await session.execute(text("SELECT version_num FROM alembic_version"))
                current_rev = result.scalar_one_or_none()
            except Exception:
                current_rev = None
    except Exception as exc:
        return False, f"Connection failed: {exc}", None, head_rev
    finally:
        if engine:
            await engine.dispose()

    if current_rev is None:
        return True, "No migrations applied (run 'gigradar db upgrade')", None, head_rev

    if current_rev == head_rev:
        return True, f"Up to date (revision: {current_rev})", current_rev, head_rev

    return (
        True,
        f"Pending migrations (current: {current_rev}, head: {head_rev})",
        current_rev,
        head_rev,
    )

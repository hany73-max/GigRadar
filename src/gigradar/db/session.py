"""Async database session and engine management for GigRadar."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from gigradar.core.settings import Settings

_GLOBAL_ENGINE: AsyncEngine | None = None
_GLOBAL_SESSION_FACTORY: async_sessionmaker[AsyncSession] | None = None


def normalize_async_database_url(url: str) -> str:
    """Normalize a database URL to use an async driver.

    Converts standard sqlite:/// or postgresql:// URLs to their async driver variants.
    """
    trimmed = url.strip()
    if trimmed.startswith("sqlite://"):
        return trimmed.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if trimmed.startswith("postgresql://"):
        return trimmed.replace("postgresql://", "postgresql+asyncpg://", 1)
    if trimmed.startswith("postgres://"):
        return trimmed.replace("postgres://", "postgresql+asyncpg://", 1)
    return trimmed


def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Apply WAL mode, busy timeout, and foreign keys on SQLite connections."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_engine_from_url(database_url: str) -> AsyncEngine:
    """Create a configured AsyncEngine for SQLite or PostgreSQL."""
    async_url = normalize_async_database_url(database_url)
    is_sqlite = "sqlite" in async_url

    engine_kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
    }

    if is_sqlite:
        from sqlalchemy.pool import NullPool

        # SQLite specific options: NullPool prevents unclosed/lingering connections across loops
        engine_kwargs["poolclass"] = NullPool
        engine = create_async_engine(async_url, **engine_kwargs)

        @event.listens_for(engine.sync_engine, "connect")
        def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
            _set_sqlite_pragmas(dbapi_connection, connection_record)

        return engine

    # PostgreSQL connection pooling options
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }
    )
    return create_async_engine(async_url, **engine_kwargs)


def get_async_engine(database_url: str | None = None) -> AsyncEngine:
    """Retrieve or create the global async engine."""
    global _GLOBAL_ENGINE, _GLOBAL_SESSION_FACTORY
    if database_url is not None:
        return create_engine_from_url(database_url)

    if _GLOBAL_ENGINE is None:
        settings = Settings()
        _GLOBAL_ENGINE = create_engine_from_url(settings.database_url)
        _GLOBAL_SESSION_FACTORY = async_sessionmaker(
            bind=_GLOBAL_ENGINE,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _GLOBAL_ENGINE


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Retrieve or create the async session factory."""
    global _GLOBAL_SESSION_FACTORY
    if engine is not None:
        return async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    if _GLOBAL_SESSION_FACTORY is None:
        eng = get_async_engine()
        _GLOBAL_SESSION_FACTORY = async_sessionmaker(
            bind=eng,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _GLOBAL_SESSION_FACTORY


@asynccontextmanager
async def get_async_session(
    engine: AsyncEngine | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async database session context."""
    session_factory = get_session_factory(engine)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Cleanly dispose of the global database engine."""
    global _GLOBAL_ENGINE, _GLOBAL_SESSION_FACTORY
    if _GLOBAL_ENGINE is not None:
        await _GLOBAL_ENGINE.dispose()
        _GLOBAL_ENGINE = None
        _GLOBAL_SESSION_FACTORY = None

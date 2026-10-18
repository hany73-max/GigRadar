"""Tests for CircuitBreaker failure tracking, cooldown recovery, and platform isolation."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from gigradar.core.models import Gig, GigStub, HealthReport
from gigradar.db.models import Base
from gigradar.db.repositories.platform_repo import PlatformRepository
from gigradar.pipeline.circuit_breaker import CircuitBreaker
from gigradar.pipeline.orchestrator import PlatformOrchestrator


class FailingClient:
    """Mock client that always raises an error."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        raise RuntimeError("Platform API 500 Internal Error")

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        raise RuntimeError("Platform API 500 Internal Error")

    async def health_check(self) -> HealthReport:
        return HealthReport(platform_id=self.name, is_healthy=False, message="Unhealthy")


class WorkingClient:
    """Mock client that always succeeds."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        return [
            GigStub(
                platform_id=self.name,
                external_id="ok_1",
                url=f"https://{self.name}.com/1",
                title="Working gig",
                detail_level="full",
            )
        ]

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        return Gig(
            platform_id=self.name,
            external_id=stub.external_id,
            url=stub.url,
            title=stub.title,
            description="Working description",
            detail_level="full",
        )

    async def health_check(self) -> HealthReport:
        return HealthReport(platform_id=self.name, is_healthy=True, message="OK")


@pytest_asyncio.fixture
async def async_db(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]], None]:
    """Create a temporary SQLite async database and initialize schema."""
    db_file = tmp_path / "test_cb.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield engine, session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_circuit_breaker_trips_after_n_failures_and_recovers_after_cooldown(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    """Circuit breaker trips after N consecutive failures and pauses platform; recovers when cooldown expires."""
    _, session_factory = async_db
    cb = CircuitBreaker(failure_threshold=3, cooldown_minutes=15)
    orchestrator = PlatformOrchestrator(circuit_breaker=cb)
    client = FailingClient(name="freelancer")

    async with session_factory() as session:
        plat_repo = PlatformRepository(session)

        # Failure 1
        res1 = await orchestrator.run_tick("freelancer", client=client, session=session)
        await session.commit()
        assert res1.success is False
        p = await plat_repo.get_by_name("freelancer")
        assert p is not None
        assert p.is_paused is False

        # Failure 2
        res2 = await orchestrator.run_tick("freelancer", client=client, session=session)
        await session.commit()
        assert res2.success is False
        p = await plat_repo.get_by_name("freelancer")
        assert p is not None
        assert p.is_paused is False

        # Failure 3 -> Trips breaker!
        res3 = await orchestrator.run_tick("freelancer", client=client, session=session)
        await session.commit()
        assert res3.success is False

        p = await plat_repo.get_by_name("freelancer")
        assert p is not None
        assert p.is_paused is True
        assert p.paused_until is not None
        assert "Consecutive failure threshold (3) reached" in (p.pause_reason or "")

        # Immediate next tick should be skipped by circuit breaker without hitting client
        res4 = await orchestrator.run_tick("freelancer", client=client, session=session)
        await session.commit()
        assert res4.paused is True
        assert res4.gigs_found == 0

        # Simulate cooldown expiration by setting paused_until in the past
        past_time = datetime.now(UTC) - timedelta(minutes=1)
        await plat_repo.set_paused(p.id, past_time, reason="Old pause")
        await session.commit()

        # Next tick should auto-recover and attempt to run again
        res5 = await orchestrator.run_tick("freelancer", client=client, session=session)
        await session.commit()
        # It executed (and failed since client still fails, rather than being skipped by paused)
        assert res5.paused is False
        assert res5.success is False


@pytest.mark.asyncio
async def test_failing_platform_does_not_block_others(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    """One failing platform does not impede or block other healthy platforms."""
    _, session_factory = async_db
    cb = CircuitBreaker(failure_threshold=2, cooldown_minutes=15)
    orchestrator = PlatformOrchestrator(circuit_breaker=cb)

    failing_client = FailingClient(name="mostaql")
    working_client = WorkingClient(name="khamsat")

    async with session_factory() as session:
        plat_repo = PlatformRepository(session)

        # 1. Failing platform ticks and fails
        res_fail = await orchestrator.run_tick("mostaql", client=failing_client, session=session)
        await session.commit()
        assert res_fail.success is False

        # 2. Healthy platform ticks and succeeds independently
        res_ok = await orchestrator.run_tick("khamsat", client=working_client, session=session)
        await session.commit()
        assert res_ok.success is True
        assert res_ok.gigs_found == 1
        assert res_ok.gigs_new == 1

        # 3. Failing platform trips circuit breaker
        await orchestrator.run_tick("mostaql", client=failing_client, session=session)
        await session.commit()

        p_mostaql = await plat_repo.get_by_name("mostaql")
        p_khamsat = await plat_repo.get_by_name("khamsat")

        assert p_mostaql is not None
        assert p_mostaql.is_paused is True

        assert p_khamsat is not None
        assert p_khamsat.is_paused is False

        # 4. Healthy platform continues working while first platform is paused
        res_ok2 = await orchestrator.run_tick("khamsat", client=working_client, session=session)
        await session.commit()
        assert res_ok2.success is True
        assert res_ok2.paused is False

"""Tests for platform orchestrator pipeline: age limits, deduplication, crash recovery, and out-of-order handling."""

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
from gigradar.db.repositories.gig_repo import GigRepository
from gigradar.pipeline.orchestrator import PlatformOrchestrator


class MockPlatformClient:
    """Mock PlatformClient recording calls and simulating platform listing & detail fetching."""

    def __init__(self, name: str, stubs: list[GigStub]) -> None:
        self.name = name
        self.stubs = stubs
        self.detail_fetch_calls: list[str] = []

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        return list(self.stubs)

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        self.detail_fetch_calls.append(stub.external_id)
        return Gig(
            platform_id=self.name,
            external_id=stub.external_id,
            url=stub.url,
            title=f"{stub.title} (Detail)",
            description="Full project description",
            budget_min=100.0,
            budget_max=200.0,
            currency="USD",
            budget_usd_est=150.0,
            bids_count=stub.bids_count or 0,
            posted_at=stub.posted_at,
            detail_level="full",
        )

    async def health_check(self) -> HealthReport:
        return HealthReport(platform_id=self.name, is_healthy=True, message="OK")


@pytest_asyncio.fixture
async def async_db(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]], None]:
    """Create a temporary SQLite async database and initialize schema."""
    db_file = tmp_path / "test_orch.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield engine, session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_first_run_mix_of_fresh_and_old_gigs(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    """First run on an empty DB with a mix of old and fresh gigs fetches details ONLY for fresh ones.

    Old gigs (> max_gig_age_minutes) are stored as stubs with processing_state='stale'.
    Gigs with unknown posted_at (None) are treated as fresh.
    """
    _, session_factory = async_db
    now = datetime.now(UTC)

    # Mostaql max_gig_age_minutes is 1440 (24h).
    fresh_stub = GigStub(
        platform_id="mostaql",
        external_id="fresh_1",
        url="https://mostaql.com/project/fresh_1",
        title="Fresh Gig (1 hour old)",
        posted_at=now - timedelta(hours=1),
        bids_count=3,
        detail_level="full",
    )
    old_stub = GigStub(
        platform_id="mostaql",
        external_id="old_1",
        url="https://mostaql.com/project/old_1",
        title="Old Stale Gig (30 hours old)",
        posted_at=now - timedelta(hours=30),
        bids_count=10,
        detail_level="full",
    )
    unknown_time_stub = GigStub(
        platform_id="mostaql",
        external_id="unknown_1",
        url="https://mostaql.com/project/unknown_1",
        title="Unknown Timestamp Gig",
        posted_at=None,
        bids_count=0,
        detail_level="full",
    )

    client = MockPlatformClient(name="mostaql", stubs=[fresh_stub, old_stub, unknown_time_stub])
    orchestrator = PlatformOrchestrator()

    async with session_factory() as session:
        result = await orchestrator.run_tick("mostaql", client=client, session=session)
        await session.commit()

        assert result.success is True
        assert result.gigs_found == 3
        assert result.gigs_new == 3

        # Details must have been fetched ONLY for fresh_1 and unknown_1, NOT old_1
        assert client.detail_fetch_calls == ["fresh_1", "unknown_1"]

        # Verify DB states
        gig_repo = GigRepository(session)
        g_fresh = await gig_repo.get_by_external_id(1, "fresh_1")
        g_old = await gig_repo.get_by_external_id(1, "old_1")
        g_unknown = await gig_repo.get_by_external_id(1, "unknown_1")

        assert g_fresh is not None
        assert g_fresh.processing_state == "detail_fetched"
        assert g_fresh.description == "Full project description"

        assert g_old is not None
        assert g_old.processing_state == "stale"
        assert g_old.budget_usd_est is None  # Detail was not fetched

        assert g_unknown is not None
        assert g_unknown.processing_state == "detail_fetched"


@pytest.mark.asyncio
async def test_detail_fetched_only_for_new_gigs(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    """Second tick with the same stubs does not re-fetch details for already-stored gigs."""
    _, session_factory = async_db
    now = datetime.now(UTC)

    stub1 = GigStub(
        platform_id="mostaql",
        external_id="gig_101",
        url="https://mostaql.com/project/101",
        title="Project 101",
        posted_at=now - timedelta(minutes=10),
        bids_count=1,
        detail_level="full",
    )
    client = MockPlatformClient(name="mostaql", stubs=[stub1])
    orchestrator = PlatformOrchestrator()

    async with session_factory() as session:
        # Tick 1: Fetches detail
        res1 = await orchestrator.run_tick("mostaql", client=client, session=session)
        await session.commit()
        assert res1.gigs_new == 1
        assert client.detail_fetch_calls == ["gig_101"]

        # Tick 2: Same stub, already stored -> 0 new, 0 detail calls
        client.detail_fetch_calls.clear()
        res2 = await orchestrator.run_tick("mostaql", client=client, session=session)
        await session.commit()
        assert res2.gigs_found == 1
        assert res2.gigs_new == 0
        assert client.detail_fetch_calls == []


@pytest.mark.asyncio
async def test_khamsat_out_of_order_listing_no_early_exit(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    """Khamsat listings are sorted by activity, so known IDs appear before new IDs.

    The orchestrator must process every row and never stop early on a known ID.
    """
    _, session_factory = async_db
    now = datetime.now(UTC)

    # Initial gig
    known_stub = GigStub(
        platform_id="khamsat",
        external_id="known_500",
        url="https://khamsat.com/community/requests/500",
        title="Known older request",
        posted_at=now - timedelta(hours=2),
        detail_level="title_only",
    )
    new_stub_after_known = GigStub(
        platform_id="khamsat",
        external_id="new_600",
        url="https://khamsat.com/community/requests/600",
        title="Brand new request appearing after known one",
        posted_at=now - timedelta(minutes=5),
        detail_level="title_only",
    )

    client1 = MockPlatformClient(name="khamsat", stubs=[known_stub])
    orchestrator = PlatformOrchestrator()

    async with session_factory() as session:
        # Store known_500 first
        await orchestrator.run_tick("khamsat", client=client1, session=session)
        await session.commit()

        # Run tick where known_500 is listed FIRST, followed by new_600
        client2 = MockPlatformClient(name="khamsat", stubs=[known_stub, new_stub_after_known])
        res2 = await orchestrator.run_tick("khamsat", client=client2, session=session)
        await session.commit()

        assert res2.gigs_found == 2
        assert res2.gigs_new == 1

        gig_repo = GigRepository(session)
        g_new = await gig_repo.get_by_external_id(1, "new_600")
        assert g_new is not None
        assert g_new.processing_state == "detail_fetched"


@pytest.mark.asyncio
async def test_crash_safety_tick_killed_halfway_completed_by_next_tick(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    """If a tick stores a gig as 'new' but crashes before detail fetching, the next tick completes it."""
    _, session_factory = async_db
    now = datetime.now(UTC)

    stub = GigStub(
        platform_id="freelancer",
        external_id="crash_proj_1",
        url="https://freelancer.com/projects/crash_1",
        title="Crashed Gig",
        posted_at=now - timedelta(minutes=15),
        bids_count=2,
        detail_level="full",
    )

    async with session_factory() as session:
        gig_repo = GigRepository(session)
        # Simulate an interrupted tick: gig was inserted with processing_state="new"
        # and session committed before detail was fetched
        gig, _ = await gig_repo.upsert_stub(1, stub, processing_state="new")
        await session.commit()
        assert gig.processing_state == "new"

    # Next tick runs with a working client
    client = MockPlatformClient(name="freelancer", stubs=[])
    orchestrator = PlatformOrchestrator()

    async with session_factory() as session:
        res = await orchestrator.run_tick("freelancer", client=client, session=session)
        await session.commit()

        assert res.success is True
        # Next tick should have fetched detail for crash_proj_1
        assert client.detail_fetch_calls == ["crash_proj_1"]

        gig_repo = GigRepository(session)
        recovered_gig = await gig_repo.get_by_external_id(1, "crash_proj_1")
        assert recovered_gig is not None
        assert recovered_gig.processing_state == "detail_fetched"
        assert recovered_gig.description == "Full project description"

"""Tests for database models and repositories (PlatformRepository, GigRepository, ScrapeRunRepository)."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from gigradar.core.models import Gig as DomainGig
from gigradar.core.models import GigStub
from gigradar.db.models import Base
from gigradar.db.repositories.gig_repo import GigRepository
from gigradar.db.repositories.platform_repo import PlatformRepository
from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository


@pytest_asyncio.fixture
async def async_db(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]], None]:
    """Create a temporary SQLite async database and initialize schema."""
    from gigradar.db.session import create_engine_from_url

    db_file = tmp_path / "test_repo.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_file}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield engine, session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_platform_repository(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = async_db
    async with session_factory() as session:
        repo = PlatformRepository(session)

        # 1. get_or_create new platform
        p1, created = await repo.get_or_create("mostaql", "https://mostaql.com")
        assert created is True
        assert p1.id is not None
        assert p1.name == "mostaql"
        assert p1.is_paused is False

        # 2. get_or_create existing platform (idempotent)
        p1_dup, created_dup = await repo.get_or_create("Mostaql", "https://mostaql.com")
        assert created_dup is False
        assert p1_dup.id == p1.id

        # 3. set_paused and clear_paused
        pause_until = datetime.now(UTC) + timedelta(minutes=15)
        await repo.set_paused(p1.id, pause_until, reason="Test pause")
        await session.commit()

        p1_paused = await repo.get_by_id(p1.id)
        assert p1_paused is not None
        assert p1_paused.is_paused is True
        assert p1_paused.pause_reason == "Test pause"

        await repo.clear_paused(p1.id)
        await session.commit()

        p1_cleared = await repo.get_by_id(p1.id)
        assert p1_cleared is not None
        assert p1_cleared.is_paused is False
        assert p1_cleared.paused_until is None


@pytest.mark.asyncio
async def test_gig_repository_idempotent_upsert_and_snapshots(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = async_db
    async with session_factory() as session:
        plat_repo = PlatformRepository(session)
        gig_repo = GigRepository(session)

        platform, _ = await plat_repo.get_or_create("mostaql", "https://mostaql.com")
        now = datetime.now(UTC)

        stub = GigStub(
            platform_id="mostaql",
            external_id="12345",
            url="https://mostaql.com/project/12345",
            title="Initial Title",
            bids_count=2,
            posted_at=now,
            client_name="Client A",
            detail_level="full",
        )

        # 1. First upsert -> new gig created with snapshot
        gig1, is_new = await gig_repo.upsert_stub(platform.id, stub)
        await session.commit()
        assert is_new is True
        assert gig1.external_id == "12345"
        assert gig1.bids_count == 2
        assert gig1.processing_state == "new"

        first_seen = gig1.first_seen_at
        assert gig1.last_seen_at is not None

        # Verify initial snapshot
        snapshots_res = await gig_repo.get_snapshots(gig1.id)
        assert len(snapshots_res) == 1
        assert snapshots_res[0].bids_count == 2

        # 2. Second upsert with identical bids_count -> same row, no new snapshot
        stub_same = GigStub(
            platform_id="mostaql",
            external_id="12345",
            url="https://mostaql.com/project/12345",
            title="Initial Title",
            bids_count=2,
            posted_at=now,
            detail_level="full",
        )
        gig2, is_new2 = await gig_repo.upsert_stub(platform.id, stub_same)
        await session.commit()
        assert is_new2 is False
        assert gig2.id == gig1.id
        assert gig2.first_seen_at == first_seen

        # Snapshot count should remain 1
        snapshots_after_same = await gig_repo.get_snapshots(gig1.id)
        assert len(snapshots_after_same) == 1

        # 3. Third upsert with changed bids_count -> snapshot added
        stub_more_bids = GigStub(
            platform_id="mostaql",
            external_id="12345",
            url="https://mostaql.com/project/12345",
            title="Initial Title",
            bids_count=5,
            posted_at=now,
            detail_level="full",
        )
        gig3, is_new3 = await gig_repo.upsert_stub(platform.id, stub_more_bids)
        await session.commit()
        assert is_new3 is False
        assert gig3.bids_count == 5

        snapshots_after_change = await gig_repo.get_snapshots(gig1.id)
        assert len(snapshots_after_change) == 2
        assert [s.bids_count for s in snapshots_after_change] == [2, 5]


@pytest.mark.asyncio
async def test_gig_repository_update_detail_and_incomplete(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = async_db
    async with session_factory() as session:
        plat_repo = PlatformRepository(session)
        gig_repo = GigRepository(session)

        platform, _ = await plat_repo.get_or_create("freelancer", "https://freelancer.com")

        stub = GigStub(
            platform_id="freelancer",
            external_id="proj_999",
            url="https://freelancer.com/projects/999",
            title="Build an ML pipeline",
            bids_count=1,
            detail_level="full",
        )

        gig, _ = await gig_repo.upsert_stub(platform.id, stub, processing_state="new")
        await session.commit()

        # Check incomplete gigs
        incomplete = await gig_repo.get_incomplete_gigs(platform.id)
        assert len(incomplete) == 1
        assert incomplete[0].id == gig.id

        # Update with full detail
        domain_detail = DomainGig(
            platform_id="freelancer",
            external_id="proj_999",
            url="https://freelancer.com/projects/999",
            title="Build an ML pipeline (Updated)",
            description="Detailed specifications for Python & PyTorch pipeline.",
            budget_min=200.0,
            budget_max=400.0,
            currency="USD",
            budget_min_usd=200.0,
            budget_max_usd=400.0,
            budget_usd_est=300.0,
            bids_count=3,
            client_name="Buyer X",
            tags_raw=["python", "pytorch"],
            language="en",
            project_type="fixed",
            detail_level="full",
        )

        updated_gig = await gig_repo.update_gig_detail(gig.id, domain_detail)
        await session.commit()

        assert updated_gig.processing_state == "detail_fetched"
        assert updated_gig.description == "Detailed specifications for Python & PyTorch pipeline."
        assert updated_gig.budget_usd_est == 300.0
        assert updated_gig.tags_raw_json == ["python", "pytorch"]
        assert updated_gig.bids_count == 3

        # Incomplete gigs should now be empty
        incomplete_after = await gig_repo.get_incomplete_gigs(platform.id)
        assert len(incomplete_after) == 0


@pytest.mark.asyncio
async def test_scrape_run_repository(
    async_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, session_factory = async_db
    async with session_factory() as session:
        plat_repo = PlatformRepository(session)
        run_repo = ScrapeRunRepository(session)

        platform, _ = await plat_repo.get_or_create("khamsat", "https://khamsat.com")

        # 1. Start and finish a successful run
        run1 = await run_repo.start_run(platform.id)
        await session.commit()
        assert run1.finished_at is None

        finished_run1 = await run_repo.finish_run(
            run1.id,
            gigs_found=10,
            gigs_new=3,
            errors=None,
        )
        await session.commit()
        assert finished_run1.finished_at is not None
        assert finished_run1.gigs_found == 10
        assert finished_run1.gigs_new == 3

        # 2. Start and finish a failed run
        run2 = await run_repo.start_run(platform.id)
        await session.commit()
        await run_repo.finish_run(
            run2.id,
            gigs_found=0,
            gigs_new=0,
            errors=[{"error": "Network timeout"}],
        )
        await session.commit()

        # 3. Check queries
        last_run = await run_repo.get_last_run(platform.id)
        assert last_run is not None
        assert last_run.id == run2.id

        last_success = await run_repo.get_last_successful_run(platform.id)
        assert last_success is not None
        assert last_success.id == run1.id

        consecutive_errs = await run_repo.count_consecutive_errors(platform.id)
        assert consecutive_errs == 1

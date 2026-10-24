import asyncio
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

    def __init__(
        self,
        name: str,
        stubs: list[GigStub],
        detail_delay: float = 0.0,
        fail_on_details: set[str] | None = None,
    ) -> None:
        self.name = name
        self.stubs = stubs
        self.detail_delay = detail_delay
        self.fail_on_details = fail_on_details or set()
        self.detail_fetch_calls: list[str] = []
        self.min_expected_listing_rows: int = 0

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        return list(self.stubs)

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        if self.detail_delay > 0:
            await asyncio.sleep(self.detail_delay)
        self.detail_fetch_calls.append(stub.external_id)
        if stub.external_id in self.fail_on_details:
            raise RuntimeError(f"Simulated detail fetch error for {stub.external_id}")
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

    async def close(self) -> None:
        pass


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


@pytest.mark.asyncio
async def test_concurrent_platform_ticks_no_database_locked(tmp_path: Path) -> None:
    """Two platforms ticking concurrently with delays produce no 'database is locked' and both finish."""
    from gigradar.db.session import create_engine_from_url

    db_file = tmp_path / "concurrent_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_engine_from_url(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    stubs_mostaql = [
        GigStub(
            platform_id="mostaql",
            external_id="m_1",
            url="https://mostaql.com/project/m_1",
            title="Mostaql Project 1",
            posted_at=now - timedelta(minutes=5),
            bids_count=1,
            detail_level="full",
        ),
        GigStub(
            platform_id="mostaql",
            external_id="m_2",
            url="https://mostaql.com/project/m_2",
            title="Mostaql Project 2",
            posted_at=now - timedelta(minutes=10),
            bids_count=2,
            detail_level="full",
        ),
    ]

    stubs_freelancer = [
        GigStub(
            platform_id="freelancer",
            external_id="f_1",
            url="https://freelancer.com/projects/f_1",
            title="Freelancer Project 1",
            posted_at=now - timedelta(minutes=5),
            bids_count=5,
            detail_level="full",
        ),
        GigStub(
            platform_id="freelancer",
            external_id="f_2",
            url="https://freelancer.com/projects/f_2",
            title="Freelancer Project 2",
            posted_at=now - timedelta(minutes=10),
            bids_count=6,
            detail_level="full",
        ),
    ]

    # Mostaql client sleeps 50ms between detail fetches while freelancer also ticks
    client_mostaql = MockPlatformClient("mostaql", stubs=stubs_mostaql, detail_delay=0.05)
    client_freelancer = MockPlatformClient("freelancer", stubs=stubs_freelancer, detail_delay=0.01)

    orchestrator = PlatformOrchestrator(engine=engine)

    try:
        # Run both ticks concurrently
        res_m, res_f = await asyncio.gather(
            orchestrator.run_tick("mostaql", client=client_mostaql),
            orchestrator.run_tick("freelancer", client=client_freelancer),
        )

        assert res_m.success is True
        assert res_m.gigs_new == 2
        assert res_f.success is True
        assert res_f.gigs_new == 2

        # Verify all 4 gigs were saved with detail_fetched
        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
        async with session_factory() as session:
            from gigradar.db.repositories.platform_repo import PlatformRepository

            plat_repo = PlatformRepository(session)
            p_m = await plat_repo.get_by_name("mostaql")
            p_f = await plat_repo.get_by_name("freelancer")
            assert p_m is not None
            assert p_f is not None

            repo = GigRepository(session)
            m1 = await repo.get_by_external_id(p_m.id, "m_1")
            m2 = await repo.get_by_external_id(p_m.id, "m_2")
            f1 = await repo.get_by_external_id(p_f.id, "f_1")
            f2 = await repo.get_by_external_id(p_f.id, "f_2")

            assert m1 is not None and m1.processing_state == "detail_fetched"
            assert m2 is not None and m2.processing_state == "detail_fetched"
            assert f1 is not None and f1.processing_state == "detail_fetched"
            assert f2 is not None and f2.processing_state == "detail_fetched"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_exception_after_first_detail_fetch_retains_completed_gigs(tmp_path: Path) -> None:
    """An unhandled crash mid-tick keeps already stored gigs in detail_fetched; next tick completes the rest."""
    from gigradar.db.session import create_engine_from_url

    db_file = tmp_path / "mid_tick_crash.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_engine_from_url(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    stubs = [
        GigStub(
            platform_id="mostaql",
            external_id="proj_1",
            url="https://mostaql.com/project/proj_1",
            title="First Project",
            posted_at=now - timedelta(minutes=10),
            detail_level="full",
        ),
        GigStub(
            platform_id="mostaql",
            external_id="proj_2",
            url="https://mostaql.com/project/proj_2",
            title="Second Project",
            posted_at=now - timedelta(minutes=10),
            detail_level="full",
        ),
    ]

    class CrashingClient(MockPlatformClient):
        async def fetch_gig_detail(self, stub: GigStub) -> Gig:
            if stub.external_id == "proj_2":
                raise KeyboardInterrupt("Simulated sudden kill mid-tick")
            return await super().fetch_gig_detail(stub)

    client_crash = CrashingClient("mostaql", stubs=stubs)
    orchestrator = PlatformOrchestrator(engine=engine)

    try:
        # Tick 1 crashes on proj_2
        with pytest.raises(KeyboardInterrupt):
            await orchestrator.run_tick("mostaql", client=client_crash)

        session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
        async with session_factory() as session:
            repo = GigRepository(session)
            # proj_1 was committed immediately after its detail fetch
            p1 = await repo.get_by_external_id(1, "proj_1")
            assert p1 is not None
            assert p1.processing_state == "detail_fetched"

            # proj_2 was committed in the batch upsert as 'new'
            p2 = await repo.get_by_external_id(1, "proj_2")
            assert p2 is not None
            assert p2.processing_state == "new"

        # Tick 2 runs with a healthy client
        client_healthy = MockPlatformClient("mostaql", stubs=[])
        res2 = await orchestrator.run_tick("mostaql", client=client_healthy)
        assert res2.success is True

        # Only proj_2 should have been fetched; proj_1 was NOT re-fetched
        assert client_healthy.detail_fetch_calls == ["proj_2"]

        async with session_factory() as session:
            repo = GigRepository(session)
            p2_done = await repo.get_by_external_id(1, "proj_2")
            assert p2_done is not None
            assert p2_done.processing_state == "detail_fetched"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_leftover_new_gigs_marked_stale_if_now_aged(tmp_path: Path) -> None:
    """Before fetching details for leftover 'new' gigs, age check marks aged gigs 'stale' without fetching."""
    from gigradar.db.session import create_engine_from_url

    db_file = tmp_path / "leftover_age_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_engine_from_url(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    # Stored 25 hours ago (> Mostaql max_gig_age_minutes: 1440)
    aged_stub = GigStub(
        platform_id="mostaql",
        external_id="aged_leftover_1",
        url="https://mostaql.com/project/aged_1",
        title="Aged Leftover Project",
        posted_at=now - timedelta(hours=25),
        detail_level="full",
    )

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
    async with session_factory() as session:
        from gigradar.db.repositories.platform_repo import PlatformRepository

        plat_repo = PlatformRepository(session)
        p, _ = await plat_repo.get_or_create("mostaql", "https://mostaql.com")
        repo = GigRepository(session)
        await repo.upsert_stub(p.id, aged_stub, processing_state="new")
        await session.commit()

    client = MockPlatformClient("mostaql", stubs=[])
    orchestrator = PlatformOrchestrator(engine=engine)

    try:
        res = await orchestrator.run_tick("mostaql", client=client)
        assert res.success is True
        # Details must NOT be fetched for aged gig
        assert client.detail_fetch_calls == []

        async with session_factory() as session:
            repo = GigRepository(session)
            gig = await repo.get_by_external_id(1, "aged_leftover_1")
            assert gig is not None
            assert gig.processing_state == "stale"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_failure_policy_max_detail_attempts_and_breaker(tmp_path: Path) -> None:
    """Test failure policy: detail_attempts, marking detail_failed after max attempts, and breaker rules."""
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.session import create_engine_from_url

    db_file = tmp_path / "failure_policy.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    engine = create_engine_from_url(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    stub_fail = GigStub(
        platform_id="mostaql",
        external_id="fail_gig_1",
        url="https://mostaql.com/project/fail_1",
        title="Failing Project",
        posted_at=now - timedelta(minutes=5),
        detail_level="full",
    )

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession)
    orchestrator = PlatformOrchestrator(engine=engine, max_detail_attempts=2)

    try:
        # Tick 1: single detail fetch fails. Does NOT count as a platform failure (attempts < 2)
        client_fail_1 = MockPlatformClient(
            "mostaql", stubs=[stub_fail], fail_on_details={"fail_gig_1"}
        )
        res1 = await orchestrator.run_tick("mostaql", client=client_fail_1)
        # Breaker does NOT trip for single detail failure
        assert res1.success is True

        async with session_factory() as session:
            from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository

            plat_repo = PlatformRepository(session)
            plat = await plat_repo.get_by_id(1)
            assert plat is not None
            assert plat.is_paused is False

            scrape_repo = ScrapeRunRepository(session)
            consecutive = await scrape_repo.count_consecutive_errors(1)
            assert consecutive == 0  # not a platform failure

            gig_repo = GigRepository(session)
            g1 = await gig_repo.get_by_external_id(1, "fail_gig_1")
            assert g1 is not None
            assert g1.detail_attempts == 1
            assert g1.processing_state == "new"  # retriable

        # Tick 2: second failure reaches max_detail_attempts (2).
        # Should transition to 'detail_failed' and not count as platform failure
        client_fail_2 = MockPlatformClient("mostaql", stubs=[], fail_on_details={"fail_gig_1"})
        res2 = await orchestrator.run_tick("mostaql", client=client_fail_2)
        assert res2.success is True

        async with session_factory() as session:
            gig_repo = GigRepository(session)
            g2 = await gig_repo.get_by_external_id(1, "fail_gig_1")
            assert g2 is not None
            assert g2.detail_attempts == 2
            assert g2.processing_state == "detail_failed"

        # Tick 3: gig in 'detail_failed' state is NO LONGER retried
        client_fail_3 = MockPlatformClient("mostaql", stubs=[])
        res3 = await orchestrator.run_tick("mostaql", client=client_fail_3)
        assert res3.success is True
        assert client_fail_3.detail_fetch_calls == []

        # Part 2: At least 2 detail fetches attempted in the tick and ALL failed -> platform failure
        stub_a = GigStub(
            platform_id="mostaql",
            external_id="all_fail_a",
            url="https://mostaql.com/project/a",
            title="A",
            posted_at=now - timedelta(minutes=5),
            detail_level="full",
        )
        stub_b = GigStub(
            platform_id="mostaql",
            external_id="all_fail_b",
            url="https://mostaql.com/project/b",
            title="B",
            posted_at=now - timedelta(minutes=5),
            detail_level="full",
        )
        client_all_fail = MockPlatformClient(
            "mostaql", stubs=[stub_a, stub_b], fail_on_details={"all_fail_a", "all_fail_b"}
        )
        res4 = await orchestrator.run_tick("mostaql", client=client_all_fail)
        # All 2 detail fetches failed -> circuit breaker records failure
        assert res4.success is False

        async with session_factory() as session:
            from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository

            plat_repo = PlatformRepository(session)
            plat = await plat_repo.get_by_id(1)
            assert plat is not None

            scrape_repo = ScrapeRunRepository(session)
            consecutive = await scrape_repo.count_consecutive_errors(1)
            assert consecutive == 1
    finally:
        await engine.dispose()

"""Regression tests for Phase 2 fixes:
1. Freelancer tick after a previous successful run completes without offset-naive/aware datetime error.
2. Datetimes loaded from DB are aware UTC for every model (Platform, Gig, GigSnapshot, ScrapeRun).
3. Unexpected exception inside tick leaves a finished run with error recorded and trips breaker after N ticks.
4. Interrupted-run marking at startup (finished_at NULL marked finished with errors_json explaining it).
5. CLI db stats reporting of last finished run, failed/interrupted in 24h, and last error.
"""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from gigradar.cli import app
from gigradar.core.models import Gig as CoreGig
from gigradar.core.models import GigStub
from gigradar.db.models import Base, Gig, GigSnapshot, Platform, ScrapeRun, utc_now
from gigradar.db.repositories.platform_repo import PlatformRepository
from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository
from gigradar.db.session import create_engine_from_url, get_async_session
from gigradar.pipeline.orchestrator import PlatformOrchestrator
from gigradar.pipeline.scheduler import SchedulerRunner


@pytest.mark.asyncio
async def test_freelancer_tick_after_previous_successful_run(tmp_path: Path) -> None:
    """Regression test: A Freelancer tick AFTER a previous successful run completes

    without error (previously raised 'can't compare offset-naive and offset-aware datetimes').
    """
    db_file = tmp_path / "freelancer_second_tick.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    engine = create_engine_from_url(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        orchestrator = PlatformOrchestrator(engine=engine)

        stub = GigStub(
            platform_id="freelancer",
            external_id="free-101",
            url="https://www.freelancer.com/projects/101",
            title="Python Data Scraper",
            posted_at=utc_now() - timedelta(minutes=15),
            bids_count=3,
            brief_description="Need Python scraper",
        )
        detail_gig = CoreGig(
            platform_id="freelancer",
            external_id="free-101",
            url="https://www.freelancer.com/projects/101",
            title="Python Data Scraper",
            description="Full project details for scraper",
            posted_at=utc_now() - timedelta(minutes=15),
            bids_count=3,
        )

        mock_client = AsyncMock()
        mock_client.base_url = "https://www.freelancer.com"
        mock_client.list_new_gigs = AsyncMock(return_value=[stub])
        mock_client.fetch_gig_detail = AsyncMock(return_value=detail_gig)

        # Tick 1: First run
        res1 = await orchestrator.run_tick("freelancer", client=mock_client)
        assert res1.success is True
        assert res1.gigs_found == 1
        assert res1.gigs_new == 1

        # Verify Tick 1 stored a successful run with aware UTC started_at
        async with get_async_session(engine=engine) as session:
            plat_repo = PlatformRepository(session)
            plat = await plat_repo.get_by_name("freelancer")
            assert plat is not None
            run_repo = ScrapeRunRepository(session)
            last_successful = await run_repo.get_last_successful_run(plat.id)
            assert last_successful is not None
            assert last_successful.finished_at is not None
            assert last_successful.started_at.tzinfo == UTC

        # Tick 2: Second run (must compute `since = max(cutoff, last_successful.started_at)` cleanly)
        res2 = await orchestrator.run_tick("freelancer", client=mock_client)
        assert res2.success is True
        assert res2.error is None
        assert res2.gigs_found == 1
        assert res2.gigs_new == 0  # Deduplicated

        # Verify both runs are recorded and finished
        async with get_async_session(engine=engine) as session:
            plat_repo = PlatformRepository(session)
            plat = await plat_repo.get_by_name("freelancer")
            assert plat is not None
            result = await session.execute(
                select(ScrapeRun).where(ScrapeRun.platform_id == plat.id)
            )
            all_runs = list(result.scalars().all())
            assert len(all_runs) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_all_models_datetimes_are_aware_utc(tmp_path: Path) -> None:
    """Regression test: Datetimes loaded from the DB are aware UTC for every model."""
    db_file = tmp_path / "models_utc.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    engine = create_engine_from_url(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Test both aware UTC input and naive input (which should be treated as UTC on write)
        fixed_aware = datetime(2026, 10, 18, 12, 30, 0, tzinfo=UTC)
        fixed_naive = datetime(2026, 10, 18, 14, 0, 0)  # naive

        async with get_async_session(engine=engine) as session:
            # 1. Platform
            plat = Platform(
                name="test_platform",
                base_url="https://example.com",
                is_paused=True,
                paused_until=fixed_aware,
                created_at=fixed_naive,  # Naive on write
            )
            session.add(plat)
            await session.flush()

            # 2. Gig
            gig = Gig(
                platform_id=plat.id,
                external_id="gig-utc-1",
                url="https://example.com/1",
                title="Test Gig",
                posted_at=fixed_naive,  # Naive on write
                first_seen_at=fixed_aware,
                last_seen_at=fixed_aware,
            )
            session.add(gig)
            await session.flush()

            # 3. GigSnapshot
            snap = GigSnapshot(
                gig_id=gig.id,
                bids_count=5,
                seen_at=fixed_naive,
            )
            session.add(snap)
            await session.flush()

            # 4. ScrapeRun
            run = ScrapeRun(
                platform_id=plat.id,
                started_at=fixed_naive,
                finished_at=fixed_aware,
                gigs_found=10,
                gigs_new=2,
            )
            session.add(run)
            await session.commit()

        # Re-query in a brand new session and verify every datetime column
        async with get_async_session(engine=engine) as session:
            # Platform checks
            plat_db = (
                await session.execute(select(Platform).where(Platform.name == "test_platform"))
            ).scalar_one()
            assert plat_db.created_at.tzinfo is not None
            assert plat_db.created_at.tzinfo == UTC
            assert plat_db.paused_until is not None
            assert plat_db.paused_until.tzinfo is not None
            assert plat_db.paused_until.tzinfo == UTC
            assert plat_db.created_at.astimezone(UTC).hour == 14

            # Gig checks
            gig_db = (
                await session.execute(select(Gig).where(Gig.external_id == "gig-utc-1"))
            ).scalar_one()
            assert gig_db.posted_at is not None
            assert gig_db.posted_at.tzinfo is not None
            assert gig_db.posted_at.tzinfo == UTC
            assert gig_db.first_seen_at.tzinfo is not None
            assert gig_db.first_seen_at.tzinfo == UTC
            assert gig_db.last_seen_at.tzinfo is not None
            assert gig_db.last_seen_at.tzinfo == UTC
            # .astimezone(UTC) preserves wall time without local timezone offset shifting
            assert gig_db.posted_at.astimezone(UTC).hour == 14

            # GigSnapshot checks
            snap_db = (
                await session.execute(select(GigSnapshot).where(GigSnapshot.gig_id == gig_db.id))
            ).scalar_one()
            assert snap_db.seen_at.tzinfo is not None
            assert snap_db.seen_at.tzinfo == UTC

            # ScrapeRun checks
            run_db = (
                await session.execute(select(ScrapeRun).where(ScrapeRun.platform_id == plat_db.id))
            ).scalar_one()
            assert run_db.started_at.tzinfo is not None
            assert run_db.started_at.tzinfo == UTC
            assert run_db.finished_at is not None
            assert run_db.finished_at.tzinfo is not None
            assert run_db.finished_at.tzinfo == UTC
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unexpected_exception_finishes_run_and_trips_breaker(tmp_path: Path) -> None:
    """Regression test: An unexpected exception inside a tick leaves a finished run

    with error recorded, records failure in circuit breaker, and trips after N ticks.
    """
    db_file = tmp_path / "unexpected_exception.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    engine = create_engine_from_url(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        orchestrator = PlatformOrchestrator(engine=engine)

        mock_client = AsyncMock()
        mock_client.base_url = "https://freelancer.com"
        # Mock an unexpected crash in listing
        mock_client.list_new_gigs = AsyncMock(
            side_effect=RuntimeError("Unrecoverable parsing crash!")
        )

        # 3 consecutive failing ticks
        for i in range(1, 4):
            res = await orchestrator.run_tick("freelancer", client=mock_client)
            assert res.success is False
            assert "Unrecoverable parsing crash!" in (res.error or "")

            # Verify that every scrape_run was marked finished and has errors recorded
            async with get_async_session(engine=engine) as session:
                plat_repo = PlatformRepository(session)
                plat = await plat_repo.get_by_name("freelancer")
                assert plat is not None
                run_repo = ScrapeRunRepository(session)
                last_run = await run_repo.get_last_run(plat.id)
                assert last_run is not None
                assert last_run.finished_at is not None
                assert last_run.errors_json is not None
                assert any(
                    "Unrecoverable parsing crash!" in str(e.get("error", ""))
                    for e in last_run.errors_json
                )
                consecutive = await run_repo.count_consecutive_errors(plat.id)
                assert consecutive == i

        # After 3 failures, platform should be paused by circuit breaker
        async with get_async_session(engine=engine) as session:
            plat_repo = PlatformRepository(session)
            plat = await plat_repo.get_by_name("freelancer")
            assert plat is not None
            assert plat.is_paused is True
            assert plat.pause_reason is not None

        # 4th tick: Circuit breaker should skip without running
        res4 = await orchestrator.run_tick("freelancer", client=mock_client)
        assert res4.paused is True
        assert res4.success is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_interrupted_run_marking_at_startup(tmp_path: Path) -> None:
    """Regression test: On scheduler startup, scrape_runs with finished_at NULL

    are marked as interrupted so they do not look healthy.
    """
    db_file = tmp_path / "interrupted_startup.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

    engine = create_engine_from_url(db_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Seed platform and an unfinished scrape run (simulating process crash/kill)
        async with get_async_session(engine=engine) as session:
            plat_repo = PlatformRepository(session)
            plat, _ = await plat_repo.get_or_create("freelancer", "https://freelancer.com")
            run_repo = ScrapeRunRepository(session)
            unfin_run = await run_repo.start_run(plat.id)
            await session.commit()
            run_id = unfin_run.id

        # Verify it starts with finished_at IS NULL
        async with get_async_session(engine=engine) as session:
            run_repo = ScrapeRunRepository(session)
            run_check = await run_repo.get_last_run(plat.id)
            assert run_check is not None
            assert run_check.finished_at is None

        # Instantiate SchedulerRunner and perform startup cleanup
        orchestrator = PlatformOrchestrator(engine=engine)
        runner = SchedulerRunner(orchestrator=orchestrator)
        marked_count = await runner.cleanup_interrupted_runs()
        assert marked_count == 1

        # Verify that the run is now finished and marked interrupted
        async with get_async_session(engine=engine) as session:
            run_repo = ScrapeRunRepository(session)
            run_after = await run_repo.get_last_run(plat.id)
            assert run_after is not None
            assert run_after.id == run_id
            assert run_after.finished_at is not None
            assert run_after.finished_at.tzinfo == UTC
            assert run_after.errors_json is not None
            assert any(e.get("interrupted") is True for e in run_after.errors_json)

            # Ensure get_last_successful_run does NOT return this interrupted run
            last_successful = await run_repo.get_last_successful_run(plat.id)
            assert last_successful is None
    finally:
        await engine.dispose()


def test_cli_db_stats_with_finished_and_failed_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test `gigradar db stats` displays last finished run, failed/interrupted runs,

    and the last error message.
    """
    db_file = tmp_path / "cli_stats_advanced.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    cli_runner = CliRunner()
    res_up = cli_runner.invoke(app, ["db", "upgrade"])
    assert res_up.exit_code == 0

    # Seed data directly into SQLite (simulating stored naive timestamps from live run)
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO platforms (name, base_url, is_paused, created_at) "
        "VALUES ('freelancer', 'https://freelancer.com', 0, '2026-10-18 10:00:00')"
    )
    plat_id = cur.lastrowid
    cur.execute(
        "INSERT INTO scrape_runs (platform_id, started_at, finished_at, gigs_found, gigs_new, errors_json) "
        "VALUES (?, '2026-10-18 10:00:00', '2026-10-18 10:01:00', 5, 2, ?)",
        (plat_id, '[{"error": "Simulated connection timeout"}]'),
    )
    conn.commit()
    conn.close()

    res_stats = cli_runner.invoke(app, ["db", "stats"])
    assert res_stats.exit_code == 0
    assert "freelancer" in res_stats.stdout
    assert "Failed" in res_stats.stdout
    assert "Simulated connection timeout" in res_stats.stdout

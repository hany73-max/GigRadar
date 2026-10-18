"""Scheduler runner managing per-platform polling jobs via APScheduler."""

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-untyped]

from gigradar.core.config_loader import load_platforms_config
from gigradar.db.session import dispose_engine
from gigradar.pipeline.orchestrator import PlatformOrchestrator, TickResult

logger = structlog.get_logger(__name__)


class SchedulerRunner:
    """Manages async scheduled polling jobs for all enabled platforms."""

    def __init__(self, orchestrator: PlatformOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or PlatformOrchestrator()
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    async def cleanup_interrupted_runs(self) -> int:
        """Mark any unfinished scrape_runs as interrupted on scheduler startup."""
        from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository
        from gigradar.db.session import get_async_session

        async with get_async_session(engine=self.orchestrator.engine) as session:
            repo = ScrapeRunRepository(session)
            count = await repo.mark_interrupted_runs()
            if count > 0:
                await session.commit()
                logger.warning("interrupted_runs_marked_on_startup", count=count)
            return count

    async def run_once(self) -> dict[str, TickResult]:
        """Execute a single polling tick across all enabled platforms sequentially and return results."""
        await self.cleanup_interrupted_runs()
        platforms_cfg = load_platforms_config()
        results: dict[str, TickResult] = {}

        for name, settings in platforms_cfg.platforms.items():
            if not settings.enabled:
                logger.info("platform_disabled_skipping", platform=name)
                continue

            logger.info("running_single_tick", platform=name)
            try:
                result = await self.orchestrator.run_tick(name)
                results[name] = result
            except Exception as exc:
                logger.error("single_tick_failed", platform=name, error=str(exc))
                results[name] = TickResult(
                    platform=name,
                    gigs_found=0,
                    gigs_new=0,
                    success=False,
                    error=str(exc),
                )

        return results

    def setup_jobs(self) -> None:
        """Configure jobs for each enabled platform using platforms.yaml intervals and jitter."""
        platforms_cfg = load_platforms_config()

        for name, settings in platforms_cfg.platforms.items():
            if not settings.enabled:
                continue

            poll_interval = settings.poll_interval_seconds
            jitter = float(settings.jitter_seconds_max)

            # Define per-platform runner function
            async def platform_job(plat_name: str = name) -> None:
                try:
                    await self.orchestrator.run_tick(plat_name)
                except Exception as exc:
                    logger.error("scheduled_job_failed", platform=plat_name, error=str(exc))

            trigger = IntervalTrigger(seconds=poll_interval, jitter=jitter)
            self.scheduler.add_job(
                platform_job,
                trigger=trigger,
                id=f"poll_{name}",
                name=f"Poll {settings.name}",
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
            logger.info(
                "scheduled_platform_job",
                platform=name,
                interval_seconds=poll_interval,
                jitter_seconds=jitter,
            )

    async def run_forever(self, shutdown_event: asyncio.Event | None = None) -> None:
        """Run the scheduler in the foreground until shutdown_event is set or cancelled."""
        await self.cleanup_interrupted_runs()
        self.setup_jobs()
        self.scheduler.start()
        self._is_running = True
        logger.info("scheduler_started", jobs_count=len(self.scheduler.get_jobs()))

        event = shutdown_event or asyncio.Event()

        try:
            # Also run an initial tick on startup for all enabled platforms
            logger.info("running_initial_startup_ticks")
            await self.run_once()

            # Wait until cancellation or shutdown trigger
            await event.wait()
        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("scheduler_interrupt_received")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Cleanly stop scheduler and release database / network resources."""
        if self._is_running:
            logger.info("shutting_down_scheduler")
            self.scheduler.shutdown(wait=False)
            self._is_running = False

        await dispose_engine()
        logger.info("scheduler_shutdown_complete")

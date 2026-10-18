"""Scrape run repository for tracking scraping and polling ticks."""

from datetime import datetime
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gigradar.db.models import ScrapeRun, utc_now


class ScrapeRunRepository:
    """Repository handling logging and inspection of scrape_runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_run(
        self,
        platform_id: int,
        started_at: datetime | None = None,
    ) -> ScrapeRun:
        """Record the start of a scrape run tick."""
        run = ScrapeRun(
            platform_id=platform_id,
            started_at=started_at or utc_now(),
            finished_at=None,
            gigs_found=0,
            gigs_new=0,
            errors_json=None,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish_run(
        self,
        run_id: int,
        finished_at: datetime | None = None,
        gigs_found: int = 0,
        gigs_new: int = 0,
        errors: list[dict[str, Any]] | None = None,
    ) -> ScrapeRun:
        """Mark a scrape run tick as completed with metrics and any errors."""
        result = await self.session.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise ValueError(f"Cannot finish non-existent scrape run #{run_id}")

        run.finished_at = finished_at or utc_now()
        run.gigs_found = gigs_found
        run.gigs_new = gigs_new
        run.errors_json = errors
        await self.session.flush()
        return run

    async def get_last_run(self, platform_id: int) -> ScrapeRun | None:
        """Retrieve the most recent run for a platform."""
        result = await self.session.execute(
            select(ScrapeRun)
            .where(ScrapeRun.platform_id == platform_id)
            .order_by(desc(ScrapeRun.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_last_successful_run(self, platform_id: int) -> ScrapeRun | None:
        """Retrieve the most recent run for a platform that finished without errors."""
        result = await self.session.execute(
            select(ScrapeRun)
            .where(
                ScrapeRun.platform_id == platform_id,
                ScrapeRun.finished_at.is_not(None),
                or_(
                    ScrapeRun.errors_json.is_(None),
                    ScrapeRun.errors_json == "null",
                ),
            )
            .order_by(desc(ScrapeRun.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_consecutive_errors(self, platform_id: int, limit: int = 10) -> int:
        """Count the number of consecutive completed runs that had errors, newest first."""
        result = await self.session.execute(
            select(ScrapeRun)
            .where(
                ScrapeRun.platform_id == platform_id,
                ScrapeRun.finished_at.is_not(None),
            )
            .order_by(desc(ScrapeRun.started_at))
            .limit(limit)
        )
        runs = list(result.scalars().all())
        consecutive = 0
        for run in runs:
            if run.errors_json:
                consecutive += 1
            else:
                break
        return consecutive

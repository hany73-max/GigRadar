"""Orchestrator pipeline executing single platform polling ticks with deduplication and crash recovery."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gigradar.core.config_loader import load_platforms_config, load_rules_config
from gigradar.core.models import GigStub
from gigradar.db.models import utc_now
from gigradar.db.repositories.gig_repo import GigRepository
from gigradar.db.repositories.platform_repo import PlatformRepository
from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository
from gigradar.db.session import get_async_session
from gigradar.pipeline.circuit_breaker import CircuitBreaker
from gigradar.platforms import (
    BlockedByBotProtection,
    FreelancerClient,
    KhamsatClient,
    MostaqlClient,
    PlatformClient,
)

logger = structlog.get_logger(__name__)


@dataclass
class TickResult:
    """Outcome of a single platform orchestrator tick."""

    platform: str
    gigs_found: int
    gigs_new: int
    success: bool
    paused: bool = False
    error: str | None = None


def get_default_client(platform_name: str) -> PlatformClient:
    """Instantiate standard PlatformClient by platform name."""
    normalized = platform_name.strip().lower()
    if normalized == "mostaql":
        return MostaqlClient()
    if normalized == "khamsat":
        return KhamsatClient()
    if normalized == "freelancer":
        return FreelancerClient()
    raise ValueError(f"Unknown platform name: {platform_name}")


def get_platform_max_age_minutes(platform_name: str) -> int:
    """Retrieve max_gig_age_minutes from platforms.yaml if present, otherwise rules.yaml default."""
    try:
        platforms_cfg = load_platforms_config()
        platform_settings = platforms_cfg.platforms.get(platform_name)
        if platform_settings and platform_settings.thresholds.max_gig_age_minutes:
            return platform_settings.thresholds.max_gig_age_minutes
    except Exception as exc:
        logger.debug("failed_loading_platforms_config_for_age", error=str(exc))

    try:
        rules_cfg = load_rules_config()
        if rules_cfg and rules_cfg.thresholds.max_gig_age_minutes:
            return rules_cfg.thresholds.max_gig_age_minutes
    except Exception as exc:
        logger.debug("failed_loading_rules_config_for_age", error=str(exc))

    return 1440  # 24 hours fallback


def get_platform_min_expected_rows(platform_name: str) -> int:
    """Retrieve min_expected_listing_rows from platforms.yaml if present, default 5."""
    try:
        platforms_cfg = load_platforms_config()
        platform_settings = platforms_cfg.platforms.get(platform_name)
        if (
            platform_settings
            and platform_settings.thresholds
            and platform_settings.thresholds.min_expected_listing_rows
        ):
            return platform_settings.thresholds.min_expected_listing_rows
    except Exception as exc:
        logger.debug("failed_loading_platforms_config_for_min_rows", error=str(exc))

    return 5


class PlatformOrchestrator:
    """Executes platform polling ticks: listing -> age check -> dedupe -> detail fetch -> log."""

    def __init__(
        self,
        circuit_breaker: CircuitBreaker | None = None,
        engine: AsyncEngine | None = None,
        max_detail_attempts: int | None = None,
        clients: dict[str, PlatformClient] | None = None,
        min_expected_listing_rows: int | None = None,
    ) -> None:
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.engine = engine
        self._clients: dict[str, PlatformClient] = clients or {}
        self._platform_locks: dict[str, asyncio.Lock] = {}
        self._min_expected_listing_rows = min_expected_listing_rows
        if max_detail_attempts is not None:
            self.max_detail_attempts = max_detail_attempts
        else:
            from gigradar.core.settings import Settings

            self.max_detail_attempts = Settings().max_detail_attempts

    def get_min_expected_rows(self, platform_name: str, client: PlatformClient) -> int:
        """Resolve expected minimum listing rows for a platform."""
        if self._min_expected_listing_rows is not None:
            return self._min_expected_listing_rows
        if (
            hasattr(client, "min_expected_listing_rows")
            and client.min_expected_listing_rows is not None
        ):
            return int(client.min_expected_listing_rows)
        return get_platform_min_expected_rows(platform_name)

    def get_platform_lock(self, platform_name: str) -> asyncio.Lock:
        """Get or create per-platform asyncio.Lock preventing concurrent ticks."""
        normalized = platform_name.strip().lower()
        if normalized not in self._platform_locks:
            self._platform_locks[normalized] = asyncio.Lock()
        return self._platform_locks[normalized]

    def get_client(self, platform_name: str) -> PlatformClient:
        """Retrieve lazily created platform client, reused across ticks."""
        normalized = platform_name.strip().lower()
        if normalized not in self._clients:
            self._clients[normalized] = get_default_client(normalized)
        return self._clients[normalized]

    async def close_clients(self) -> None:
        """Close all owned platform clients and underlying HTTP pools."""
        for name, client in list(self._clients.items()):
            try:
                if hasattr(client, "close") and callable(client.close):
                    await client.close()
            except Exception as exc:
                logger.warning("error_closing_client", platform=name, error=str(exc))
        self._clients.clear()

    async def record_startup_health_failure(self, platform_name: str, error_message: str) -> None:
        """Record a platform failure in circuit breaker if startup health check fails."""
        async with get_async_session(engine=self.engine) as session:
            platform_repo = PlatformRepository(session)
            scrape_run_repo = ScrapeRunRepository(session)
            client = self.get_client(platform_name)
            base_url = getattr(client, "base_url", f"https://{platform_name}.com")
            platform, _ = await platform_repo.get_or_create(platform_name, base_url)
            await self.circuit_breaker.record_failure(
                platform_repo,
                scrape_run_repo,
                platform.id,
                f"Startup health check failed: {error_message}",
            )
            await session.commit()

    async def run_tick(
        self,
        platform_name: str,
        client: PlatformClient | None = None,
        session: AsyncSession | None = None,
    ) -> TickResult:
        """Run an isolated tick for a specific platform protected by per-platform lock."""
        normalized_name = platform_name.strip().lower()
        lock = self.get_platform_lock(normalized_name)

        async with lock:
            if session is not None:
                return await self._execute_tick(normalized_name, client, session)

            async with get_async_session(engine=self.engine) as managed_session:
                return await self._execute_tick(normalized_name, client, managed_session)

    async def _execute_tick(
        self,
        platform_name: str,
        client: PlatformClient | None,
        session: AsyncSession,
    ) -> TickResult:
        platform_repo = PlatformRepository(session)
        gig_repo = GigRepository(session)
        scrape_run_repo = ScrapeRunRepository(session)

        # 1. Resolve platform record in DB and commit immediately
        platform_client = client or self.get_client(platform_name)
        base_url = getattr(platform_client, "base_url", f"https://{platform_name}.com")
        platform, _ = await platform_repo.get_or_create(platform_name, base_url)
        await session.commit()

        # 2. Check Circuit Breaker
        can_run, pause_reason = await self.circuit_breaker.can_execute(platform_repo, platform.id)
        if not can_run:
            logger.info("tick_skipped_circuit_breaker", platform=platform_name, reason=pause_reason)
            return TickResult(
                platform=platform_name,
                gigs_found=0,
                gigs_new=0,
                success=True,
                paused=True,
                error=pause_reason,
            )

        # 3. Start scrape_runs record and commit immediately
        start_time = utc_now()
        scrape_run = await scrape_run_repo.start_run(platform.id, started_at=start_time)
        await session.commit()

        errors: list[dict[str, Any]] = []
        stubs: list[GigStub] = []
        gigs_new = 0

        try:
            max_age_minutes = get_platform_max_age_minutes(platform_name)

            # 4. Determine `since` parameter
            since: datetime | None = None
            if platform_name == "freelancer":
                max_age_cutoff = start_time - timedelta(minutes=max_age_minutes)
                last_successful = await scrape_run_repo.get_last_successful_run(platform.id)
                if last_successful is not None and last_successful.started_at is not None:
                    since = max(max_age_cutoff, last_successful.started_at)
                else:
                    since = max_age_cutoff

            # 5. List stubs from client (network call - no open write transaction!)
            listing_failed = False
            try:
                stubs = await platform_client.list_new_gigs(since=since)
            except BlockedByBotProtection as exc:
                listing_failed = True
                err_msg = f"Platform {platform_name} blocked by bot protection: {exc}"
                logger.error(
                    "tick_blocked_by_bot_protection",
                    platform=platform_name,
                    error=str(exc),
                    reason=exc.reason,
                )
                errors.append(
                    {
                        "stage": "list",
                        "error": str(exc),
                        "blocked": True,
                        "platform_failure": True,
                        "timestamp": utc_now().isoformat(),
                    }
                )
                await scrape_run_repo.finish_run(
                    scrape_run.id,
                    finished_at=utc_now(),
                    gigs_found=0,
                    gigs_new=0,
                    errors=errors,
                )
                await self.circuit_breaker.record_failure(
                    platform_repo, scrape_run_repo, platform.id, err_msg
                )
                await session.commit()
                return TickResult(
                    platform=platform_name,
                    gigs_found=0,
                    gigs_new=0,
                    success=False,
                    error=err_msg,
                )
            except Exception as exc:
                listing_failed = True
                err_msg = f"Failed listing gigs from {platform_name}: {exc}"
                logger.error("tick_list_failed", platform=platform_name, error=str(exc))
                errors.append(
                    {
                        "stage": "list",
                        "error": str(exc),
                        "platform_failure": True,
                        "timestamp": utc_now().isoformat(),
                    }
                )
                await scrape_run_repo.finish_run(
                    scrape_run.id,
                    finished_at=utc_now(),
                    gigs_found=0,
                    gigs_new=0,
                    errors=errors,
                )
                await self.circuit_breaker.record_failure(
                    platform_repo, scrape_run_repo, platform.id, err_msg
                )
                await session.commit()
                return TickResult(
                    platform=platform_name,
                    gigs_found=0,
                    gigs_new=0,
                    success=False,
                    error=err_msg,
                )

            # Check suspicious empty listings (Mostaql and Khamsat only; Freelancer is exempt)
            if platform_name in {"mostaql", "khamsat"}:
                min_rows = self.get_min_expected_rows(platform_name, platform_client)
                if len(stubs) < min_rows:
                    err_msg = (
                        f"suspicious_empty_listing on {platform_name}: found {len(stubs)} rows "
                        f"(expected >= {min_rows})"
                    )
                    logger.error(
                        "suspicious_empty_listing",
                        platform=platform_name,
                        found=len(stubs),
                        min_expected=min_rows,
                    )
                    errors.append(
                        {
                            "stage": "list",
                            "error": "suspicious_empty_listing",
                            "found": len(stubs),
                            "min_expected": min_rows,
                            "platform_failure": True,
                            "timestamp": utc_now().isoformat(),
                        }
                    )
                    await scrape_run_repo.finish_run(
                        scrape_run.id,
                        finished_at=utc_now(),
                        gigs_found=len(stubs),
                        gigs_new=0,
                        errors=errors,
                    )
                    await self.circuit_breaker.record_failure(
                        platform_repo, scrape_run_repo, platform.id, err_msg
                    )
                    await session.commit()
                    return TickResult(
                        platform=platform_name,
                        gigs_found=len(stubs),
                        gigs_new=0,
                        success=False,
                        error="suspicious_empty_listing",
                    )

            # 6. Dedupe against DB and determine fresh vs stale
            stub_lookup: dict[str, GigStub] = {}

            for stub in stubs:
                stub_lookup[stub.external_id] = stub

                # Age evaluation
                is_stale = False
                if stub.posted_at is not None:
                    posted_utc = stub.posted_at.astimezone(UTC)
                    age_minutes = (start_time - posted_utc).total_seconds() / 60.0
                    if age_minutes > max_age_minutes:
                        is_stale = True

                # Check if gig already exists in DB
                existing = await gig_repo.get_by_external_id(platform.id, stub.external_id)
                if existing is not None:
                    # Idempotent touch: updates last_seen_at and snapshots if bids changed
                    await gig_repo.upsert_stub(platform.id, stub)
                else:
                    # Brand new gig
                    target_state = "stale" if is_stale else "new"
                    await gig_repo.upsert_stub(platform.id, stub, processing_state=target_state)
                    gigs_new += 1

            # Commit after the batch of stub upserts for a listing!
            await session.commit()

            # 7. Detail fetching & crash recovery: pick up incomplete gigs (processing_state == 'new')
            incomplete_gigs = await gig_repo.get_incomplete_gigs(platform.id)

            detail_attempts_in_tick = 0
            detail_failures_in_tick = 0

            for inc_gig in incomplete_gigs:
                # Check age limit on leftover 'new' gigs before fetching details
                if inc_gig.posted_at is not None:
                    posted_utc = inc_gig.posted_at.astimezone(UTC)
                    age_min = (utc_now() - posted_utc).total_seconds() / 60.0
                    if age_min > max_age_minutes:
                        logger.info(
                            "leftover_gig_marked_stale",
                            platform=platform_name,
                            external_id=inc_gig.external_id,
                            age_minutes=age_min,
                        )
                        await gig_repo.mark_stale(inc_gig.id)
                        await session.commit()
                        continue

                if platform_name == "khamsat":
                    # Khamsat listing stub provides all available data; transition to detail_fetched
                    await gig_repo.mark_detail_fetched(inc_gig.id)
                    await session.commit()
                    continue

                # Need to fetch details for Mostaql / Freelancer
                detail_attempts_in_tick += 1
                try:
                    # Retrieve or synthesize stub for detail fetch
                    stub_for_fetch = stub_lookup.get(inc_gig.external_id)
                    if stub_for_fetch is None:
                        stub_for_fetch = GigStub(
                            platform_id=platform_name,
                            external_id=inc_gig.external_id,
                            url=inc_gig.url,
                            title=inc_gig.title,
                            posted_at=inc_gig.posted_at,
                            bids_count=inc_gig.bids_count,
                            brief_description=inc_gig.description,
                            client_name=inc_gig.client_name,
                            detail_level=inc_gig.detail_level,  # type: ignore[arg-type]
                        )

                    # Network call without open write transaction
                    detail = await platform_client.fetch_gig_detail(stub_for_fetch)
                    await gig_repo.update_gig_detail(inc_gig.id, detail)
                    # Commit after EACH gig detail update!
                    await session.commit()
                except BlockedByBotProtection as exc:
                    detail_failures_in_tick += 1
                    logger.error(
                        "tick_detail_blocked_by_bot_protection",
                        platform=platform_name,
                        external_id=inc_gig.external_id,
                        error=str(exc),
                        reason=exc.reason,
                    )
                    errors.append(
                        {
                            "stage": "detail",
                            "external_id": inc_gig.external_id,
                            "error": str(exc),
                            "blocked": True,
                            "platform_failure": True,
                            "timestamp": utc_now().isoformat(),
                        }
                    )
                    await self.circuit_breaker.record_failure(
                        platform_repo,
                        scrape_run_repo,
                        platform.id,
                        f"Blocked by bot protection during detail fetch: {exc}",
                    )
                    await gig_repo.record_detail_failure(
                        inc_gig.id, max_attempts=self.max_detail_attempts
                    )
                    await session.commit()
                except Exception as exc:
                    detail_failures_in_tick += 1
                    logger.warning(
                        "tick_detail_fetch_failed",
                        platform=platform_name,
                        external_id=inc_gig.external_id,
                        error=str(exc),
                    )
                    errors.append(
                        {
                            "stage": "detail",
                            "external_id": inc_gig.external_id,
                            "error": str(exc),
                            "platform_failure": False,
                            "timestamp": utc_now().isoformat(),
                        }
                    )
                    # Failure policy: increment attempts, mark detail_failed if max attempts reached
                    await gig_repo.record_detail_failure(
                        inc_gig.id, max_attempts=self.max_detail_attempts
                    )
                    # Commit after recording detail failure!
                    await session.commit()

            # 8. Determine platform failure per failure policy:
            # A failed detail does NOT count as a platform failure;
            # circuit breaker only records a failure when listing fails,
            # or when at least 2 detail fetches were attempted in the tick and ALL failed.
            is_platform_failure = listing_failed or (
                detail_attempts_in_tick >= 2 and detail_failures_in_tick == detail_attempts_in_tick
            )
            if is_platform_failure:
                for err in errors:
                    err["platform_failure"] = True

            # Complete scrape_runs record
            finish_time = utc_now()
            await scrape_run_repo.finish_run(
                scrape_run.id,
                finished_at=finish_time,
                gigs_found=len(stubs),
                gigs_new=gigs_new,
                errors=errors if errors else None,
            )

            # 9. Update Circuit Breaker

            if is_platform_failure:
                await self.circuit_breaker.record_failure(
                    platform_repo,
                    scrape_run_repo,
                    platform.id,
                    error_message=f"All {detail_attempts_in_tick} detail fetches failed"
                    if not listing_failed
                    else "Listing failed",
                )
            else:
                await self.circuit_breaker.record_success(platform_repo, platform.id)

            # Commit after scrape run finish and circuit breaker updates!
            await session.commit()

            logger.info(
                "tick_completed",
                platform=platform_name,
                gigs_found=len(stubs),
                gigs_new=gigs_new,
                errors_count=len(errors),
                platform_failure=is_platform_failure,
            )

            return TickResult(
                platform=platform_name,
                gigs_found=len(stubs),
                gigs_new=gigs_new,
                success=not is_platform_failure,
                error=f"{len(errors)} errors" if errors else None,
            )

        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            err_msg = f"Unexpected error in tick for {platform_name}: {exc}"
            logger.error("tick_unexpected_error", platform=platform_name, error=str(exc))
            errors.append(
                {
                    "stage": "unexpected",
                    "error": str(exc),
                    "platform_failure": True,
                    "timestamp": utc_now().isoformat(),
                }
            )
            try:
                await session.rollback()
                await scrape_run_repo.finish_run(
                    scrape_run.id,
                    finished_at=utc_now(),
                    gigs_found=len(stubs),
                    gigs_new=gigs_new,
                    errors=errors,
                )
                await self.circuit_breaker.record_failure(
                    platform_repo, scrape_run_repo, platform.id, err_msg
                )
                await session.commit()
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as cleanup_exc:
                logger.error(
                    "tick_cleanup_failed",
                    platform=platform_name,
                    error=str(cleanup_exc),
                )
            return TickResult(
                platform=platform_name,
                gigs_found=len(stubs),
                gigs_new=gigs_new,
                success=False,
                error=err_msg,
            )

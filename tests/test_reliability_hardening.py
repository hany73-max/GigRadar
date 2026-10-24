"""Comprehensive unit tests for Phase 2.5a reliability hardening."""

import asyncio
import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from gigradar.core.logging import redact_secrets, setup_logging
from gigradar.core.models import GigStub, HealthReport
from gigradar.pipeline.circuit_breaker import CircuitBreaker
from gigradar.pipeline.orchestrator import PlatformOrchestrator, TickResult
from gigradar.pipeline.scheduler import SchedulerRunner
from gigradar.platforms.common.exceptions import BlockedByBotProtection
from gigradar.platforms.common.http_client import PoliteHttpClient, RateLimiter
from gigradar.platforms.freelancer.client import FreelancerClient
from gigradar.platforms.khamsat.client import KhamsatClient
from gigradar.platforms.mostaql.client import MostaqlClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"


# ==============================================================================
# 1. Block Detection Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_http_202_raises_blocked_by_bot_protection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, text="Accepted - challenge required")

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    with pytest.raises(BlockedByBotProtection) as exc_info:
        await http_client.get("https://example.com/listing")
    assert exc_info.value.status_code == 202
    assert exc_info.value.reason == "http_202"
    await http_client.close()


@pytest.mark.asyncio
async def test_x_amzn_waf_action_header_raises_blocked_by_bot_protection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            text="Forbidden",
            headers={"x-amzn-waf-action": "captcha"},
        )

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    with pytest.raises(BlockedByBotProtection) as exc_info:
        await http_client.get("https://example.com/listing")
    assert "captcha" in (exc_info.value.reason or "")
    await http_client.close()


@pytest.mark.asyncio
async def test_cloudflare_challenge_body_marker_detected_on_empty_listing() -> None:
    cf_html = (FIXTURES_DIR / "cloudflare_challenge.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=cf_html)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = MostaqlClient(http_client=http_client)
    with pytest.raises(BlockedByBotProtection) as exc_info:
        await client.list_new_gigs()
    assert "just a moment" in str(exc_info.value).lower()
    await client.close()


@pytest.mark.asyncio
async def test_aws_waf_body_marker_detected_on_empty_listing() -> None:
    waf_html = (FIXTURES_DIR / "aws_waf_challenge.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=waf_html)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = KhamsatClient(http_client=http_client)
    with pytest.raises(BlockedByBotProtection) as exc_info:
        await client.list_new_gigs()
    assert (
        "security check" in str(exc_info.value).lower() or "awswaf" in str(exc_info.value).lower()
    )
    await client.close()


@pytest.mark.asyncio
async def test_login_page_with_captcha_script_detected_on_empty_listing() -> None:
    login_html = (FIXTURES_DIR / "login_captcha_page.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=login_html)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = MostaqlClient(http_client=http_client)
    with pytest.raises(BlockedByBotProtection) as exc_info:
        await client.list_new_gigs()
    assert "recaptcha" in str(exc_info.value).lower()
    await client.close()


@pytest.mark.asyncio
async def test_legitimate_listing_with_challenge_and_captcha_words_succeeds() -> None:
    """Legitimate listings containing the word 'challenge' or 'captcha' must NOT trigger BlockedByBotProtection."""
    legit_html = (FIXTURES_DIR / "legitimate_challenge_listing.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=legit_html)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = MostaqlClient(http_client=http_client)
    client.config.max_pages_per_run = 1
    stubs = await client.list_new_gigs()
    assert len(stubs) == 5
    # Confirm words 'challenge' and 'captcha' are present in the parsed stubs
    titles = [s.title for s in stubs]
    assert any("Challenge" in t for t in titles)
    assert any("كابتشا" in t for t in titles)
    await client.close()


@pytest.mark.asyncio
async def test_freelancer_json_api_never_scans_body_markers() -> None:
    """Freelancer JSON API responses must never trigger body marker false-positives."""
    json_payload = {
        "status": "success",
        "result": {
            "projects": [
                {
                    "id": 12345,
                    "title": "Machine learning challenge solving",
                    "preview_description": "We need help solving a captcha challenge",
                    "time_submitted": int(datetime.now(UTC).timestamp()),
                    "currency": {"code": "USD"},
                    "budget": {"minimum": 50, "maximum": 100},
                    "bid_stats": {"bid_count": 2},
                    "owner_id": 999,
                    "type": "fixed",
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json_payload)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = FreelancerClient(http_client=http_client)
    stubs = await client.list_new_gigs()
    assert len(stubs) == 1
    assert "challenge" in stubs[0].title.lower()
    await client.close()


# ==============================================================================
# 2. Suspicious Empty Listing Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mostaql_suspicious_empty_listing_fails_tick_and_records_failure(
    tmp_path: Path,
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    db_path = tmp_path / "test_suspicious.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    from gigradar.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class MockMostaqlClientWithFewGigs:
        name = "mostaql"
        base_url = "https://mostaql.com"

        async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
            # Returns only 2 gigs (< 5 min_expected_listing_rows)
            return [
                GigStub(
                    platform_id="mostaql",
                    external_id=f"10{i}",
                    url=f"https://mostaql.com/project/10{i}",
                    title=f"Gig {i}",
                )
                for i in range(2)
            ]

        async def fetch_gig_detail(self, stub: GigStub) -> Any:
            raise NotImplementedError

        async def health_check(self) -> HealthReport:
            return HealthReport(platform_id="mostaql", is_healthy=True, message="OK")

        async def close(self) -> None:
            pass

    breaker = CircuitBreaker(failure_threshold=3, cooldown_minutes=15)
    orchestrator = PlatformOrchestrator(circuit_breaker=breaker, engine=engine)

    result = await orchestrator.run_tick("mostaql", client=MockMostaqlClientWithFewGigs())
    assert result.success is False
    assert result.error == "suspicious_empty_listing"
    assert result.gigs_found == 2

    # Breaker failure recorded: consecutive failures = 1
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository
    from gigradar.db.session import get_async_session

    async with get_async_session(engine=engine) as session:
        plat_repo = PlatformRepository(session)
        run_repo = ScrapeRunRepository(session)
        plat = await plat_repo.get_by_name("mostaql")
        assert plat is not None
        consecutive = await run_repo.count_consecutive_errors(plat.id)
        assert consecutive == 1

    await orchestrator.close_clients()
    await engine.dispose()


@pytest.mark.asyncio
async def test_freelancer_exempt_from_suspicious_empty_listing(tmp_path: Path) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    db_path = tmp_path / "test_freelancer_exempt.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    from gigradar.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class MockFreelancerClientFewGigs:
        name = "freelancer"
        base_url = "https://www.freelancer.com"

        async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
            # Returns 1 gig (Freelancer is exempt, can legitimately return 0-2)
            return [
                GigStub(
                    platform_id="freelancer",
                    external_id="f1",
                    url="https://freelancer.com/projects/f1",
                    title="Freelancer Gig",
                )
            ]

        async def fetch_gig_detail(self, stub: GigStub) -> Any:
            from gigradar.core.models import Gig

            return Gig(
                platform_id="freelancer",
                external_id=stub.external_id,
                url=stub.url,
                title=stub.title,
                description="Full detail",
            )

        async def health_check(self) -> HealthReport:
            return HealthReport(platform_id="freelancer", is_healthy=True, message="OK")

        async def close(self) -> None:
            pass

    breaker = CircuitBreaker()
    orchestrator = PlatformOrchestrator(circuit_breaker=breaker, engine=engine)

    result = await orchestrator.run_tick("freelancer", client=MockFreelancerClientFewGigs())
    assert result.success is True
    assert result.gigs_found == 1

    await orchestrator.close_clients()
    await engine.dispose()


# ==============================================================================
# 3. Secret-Safe Logging & Redaction Tests
# ==============================================================================


def test_secret_redaction_telegram_token() -> None:
    raw_url = "https://api.telegram.org/bot123456789:ABCdefGHI-jkl_mnoPQR/getUpdates"
    redacted = redact_secrets(raw_url)
    assert "ABCdefGHI-jkl_mnoPQR" not in redacted
    assert "bot123456789:[REDACTED]/getUpdates" in redacted


def test_secret_redaction_query_params() -> None:
    query_url = "https://example.com/api?token=secret12345&key=AIzaSySecret999&normal_param=hello"
    redacted = redact_secrets(query_url)
    assert "secret12345" not in redacted
    assert "AIzaSySecret999" not in redacted
    assert "token=[REDACTED]" in redacted
    assert "key=[REDACTED]" in redacted
    assert "normal_param=hello" in redacted


def test_logging_redaction_in_stdlib_and_exception_traceback() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    import structlog

    from gigradar.core.logging import RedactingFilter, RedactingProcessorFormatter

    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    formatter = RedactingProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )
    handler.setFormatter(formatter)
    handler.addFilter(RedactingFilter())

    test_logger = logging.getLogger("test_redact_logger")
    test_logger.handlers.clear()
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    # 1. Stdlib log line with token
    test_logger.info(
        "Connecting to https://api.telegram.org/bot123456789:ABCdefGHI-jkl_mnoPQR/getUpdates"
    )

    # 2. Exception traceback containing token
    try:
        raise RuntimeError(
            "Failure contacting https://api.telegram.org/bot123456789:ABCdefGHI-jkl_mnoPQR/sendMessage"
        )
    except RuntimeError:
        test_logger.exception("Handled call error")

    output = stream.getvalue()
    assert "ABCdefGHI-jkl_mnoPQR" not in output
    assert "bot123456789:[REDACTED]" in output


def test_logger_levels_warning() -> None:
    setup_logging(log_level="INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("alembic").level == logging.WARNING


# ==============================================================================
# 4. Client Lifecycle & Leak Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_orchestrator_reuses_client_and_closes_on_shutdown() -> None:
    closed_called = False

    class MockClient:
        name = "mock_plat"
        base_url = "https://mock.com"

        async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
            return [
                GigStub(
                    platform_id="mock_plat",
                    external_id=f"m{i}",
                    url=f"https://mock.com/m{i}",
                    title=f"Title {i}",
                )
                for i in range(5)
            ]

        async def fetch_gig_detail(self, stub: GigStub) -> Any:
            from gigradar.core.models import Gig

            return Gig(
                platform_id="mock_plat",
                external_id=stub.external_id,
                url=stub.url,
                title=stub.title,
                description="Desc",
            )

        async def health_check(self) -> HealthReport:
            return HealthReport(platform_id="mock_plat", is_healthy=True, message="OK")

        async def close(self) -> None:
            nonlocal closed_called
            closed_called = True

    mock_client = MockClient()
    orchestrator = PlatformOrchestrator(clients={"mostaql": mock_client})

    # Verify get_client returns the exact same instance repeatedly
    c1 = orchestrator.get_client("mostaql")
    c2 = orchestrator.get_client("mostaql")
    assert c1 is c2
    assert c1 is mock_client

    # Verify close_clients invokes close()
    await orchestrator.close_clients()
    assert closed_called is True
    assert len(orchestrator._clients) == 0


# ==============================================================================
# 5. Concurrency Guard & Lock Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_per_platform_lock_prevents_concurrent_ticks_on_same_platform(tmp_path: Path) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    db_path = tmp_path / "test_concurrency.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    from gigradar.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    execution_order: list[str] = []

    class MockSlowClient:
        name = "mostaql"
        base_url = "https://mostaql.com"

        async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
            execution_order.append("start_list")
            await asyncio.sleep(0.05)
            execution_order.append("end_list")
            return [
                GigStub(
                    platform_id="mostaql",
                    external_id=f"g{i}",
                    url=f"https://mostaql.com/g{i}",
                    title=f"G{i}",
                )
                for i in range(5)
            ]

        async def fetch_gig_detail(self, stub: GigStub) -> Any:
            from gigradar.core.models import Gig

            return Gig(
                platform_id="mostaql",
                external_id=stub.external_id,
                url=stub.url,
                title=stub.title,
                description="Desc",
            )

        async def health_check(self) -> HealthReport:
            return HealthReport(platform_id="mostaql", is_healthy=True, message="OK")

        async def close(self) -> None:
            pass

    orchestrator = PlatformOrchestrator(engine=engine)
    client = MockSlowClient()

    # Schedule two concurrent ticks on the same platform
    t1 = asyncio.create_task(orchestrator.run_tick("mostaql", client=client))
    t2 = asyncio.create_task(orchestrator.run_tick("mostaql", client=client))

    res1, res2 = await asyncio.gather(t1, t2)
    assert res1.success is True
    assert res2.success is True

    # Lock ensures tick 1 completely finished its listing before tick 2 started its listing
    assert execution_order == ["start_list", "end_list", "start_list", "end_list"]

    await orchestrator.close_clients()
    await engine.dispose()


# ==============================================================================
# 6. Scheduler Coverage & Lifecycle Tests (Target >= 80%)
# ==============================================================================


@pytest.mark.asyncio
async def test_scheduler_setup_jobs_staggered() -> None:
    runner = SchedulerRunner()
    runner.setup_jobs()

    jobs = runner.scheduler.get_jobs()
    assert len(jobs) >= 2  # Mostaql, Khamsat, Freelancer

    # Confirm jobs have next_run_time set in the future and staggered
    next_times = [j.next_run_time for j in jobs if j.next_run_time is not None]
    assert len(next_times) == len(jobs)
    # Ensure they are not identical (staggered)
    unique_seconds = {t.timestamp() for t in next_times}
    assert len(unique_seconds) > 1

    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_startup_health_checks_unhealthy_records_failure() -> None:
    class MockUnhealthyClient:
        async def health_check(self) -> HealthReport:
            return HealthReport(
                platform_id="mock", is_healthy=False, message="Challenge encountered"
            )

        async def close(self) -> None:
            pass

    recorded_failure = False

    class MockOrchestrator(PlatformOrchestrator):
        def get_client(self, platform_name: str) -> Any:
            return MockUnhealthyClient()

        async def record_startup_health_failure(
            self, platform_name: str, error_message: str
        ) -> None:
            nonlocal recorded_failure
            recorded_failure = True

    orch = MockOrchestrator()
    runner = SchedulerRunner(orchestrator=orch)

    # Health check must never raise an unhandled error or crash
    results = await runner.startup_health_checks()
    assert recorded_failure is True
    assert all(status is False for status in results.values())

    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_run_forever_and_clean_shutdown() -> None:
    ticks_called: list[str] = []

    class FakeOrchestrator(PlatformOrchestrator):
        async def run_tick(
            self,
            platform_name: str,
            client: Any = None,
            session: Any = None,
            **kwargs: Any,
        ) -> TickResult:
            ticks_called.append(platform_name)
            return TickResult(platform=platform_name, gigs_found=5, gigs_new=0, success=True)

        async def record_startup_health_failure(
            self, platform_name: str, error_message: str
        ) -> None:
            pass

        def get_client(self, platform_name: str) -> Any:
            class DummyClient:
                async def health_check(self) -> HealthReport:
                    return HealthReport(platform_id=platform_name, is_healthy=True, message="OK")

                async def close(self) -> None:
                    pass

            return DummyClient()

    fake_orch = FakeOrchestrator()
    runner = SchedulerRunner(orchestrator=fake_orch)

    shutdown_event = asyncio.Event()

    # Trigger shutdown after short delay
    async def trigger_shutdown() -> None:
        await asyncio.sleep(0.05)
        shutdown_event.set()

    shutdown_task = asyncio.create_task(trigger_shutdown())
    await runner.run_forever(shutdown_event=shutdown_event)
    await shutdown_task

    assert runner._is_running is False


@pytest.mark.asyncio
async def test_scheduler_run_once_with_exceptions() -> None:
    class FailingOrchestrator(PlatformOrchestrator):
        async def run_tick(
            self,
            platform_name: str,
            client: Any = None,
            session: Any = None,
            **kwargs: Any,
        ) -> TickResult:
            raise RuntimeError("Database unavailable")

    runner = SchedulerRunner(orchestrator=FailingOrchestrator())
    results = await runner.run_once()
    assert len(results) >= 2
    for _plat, res in results.items():
        assert res.success is False
        assert "Database unavailable" in str(res.error)
    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_platform_job_callback() -> None:
    calls: list[str] = []

    class MockOrchestrator(PlatformOrchestrator):
        async def run_tick(
            self,
            platform_name: str,
            client: Any = None,
            session: Any = None,
            **kwargs: Any,
        ) -> TickResult:
            calls.append(platform_name)
            if platform_name == "khamsat":
                raise RuntimeError("Khamsat network blip")
            return TickResult(platform=platform_name, gigs_found=5, gigs_new=0, success=True)

    orch = MockOrchestrator()
    runner = SchedulerRunner(orchestrator=orch)
    runner.setup_jobs()

    # Invoke the registered job functions directly
    jobs = runner.scheduler.get_jobs()
    for job in jobs:
        await job.func()

    assert "mostaql" in calls
    assert "khamsat" in calls
    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_run_forever_cancelled_task() -> None:
    class DummyOrch(PlatformOrchestrator):
        async def run_tick(
            self,
            platform_name: str,
            client: Any = None,
            session: Any = None,
            **kwargs: Any,
        ) -> TickResult:
            return TickResult(platform=platform_name, gigs_found=0, gigs_new=0, success=True)

        def get_client(self, platform_name: str) -> Any:
            class DummyClient:
                async def health_check(self) -> HealthReport:
                    return HealthReport(platform_id=platform_name, is_healthy=True, message="OK")

                async def close(self) -> None:
                    pass

            return DummyClient()

    runner = SchedulerRunner(orchestrator=DummyOrch())
    forever_task = asyncio.create_task(runner.run_forever())
    await asyncio.sleep(0.05)
    forever_task.cancel()
    await forever_task
    assert runner._is_running is False

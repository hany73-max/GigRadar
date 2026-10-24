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


def test_secret_redaction_bare_key_assignments() -> None:
    text = "Connecting with token=secret_token_12345 and api_key='secret_api_key_6789' and key: secret_key_9999"
    redacted = redact_secrets(text)
    assert "secret_token_12345" not in redacted
    assert "secret_api_key_6789" not in redacted
    assert "secret_key_9999" not in redacted
    assert "token=[REDACTED]" in redacted
    assert "api_key='[REDACTED]'" in redacted
    assert "key: [REDACTED]" in redacted


def test_secret_redaction_headers() -> None:
    header_text = (
        "Headers: Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test and "
        "x-goog-api-key: my_google_secret_key_12345"
    )
    redacted = redact_secrets(header_text)
    assert "Bearer eyJhbGciOiJIUzI1NiJ9.test" not in redacted
    assert "Authorization: Bearer [REDACTED]" in redacted
    assert "my_google_secret_key_12345" not in redacted
    assert "x-goog-api-key: [REDACTED]" in redacted


def test_secret_redaction_google_key_patterns() -> None:
    valid_aiza = "AIza" + "A" * 35
    valid_aq = "AQ." + "B" * 20
    text = f"Keys found: {valid_aiza} and {valid_aq}"
    redacted = redact_secrets(text)
    assert valid_aiza not in redacted
    assert valid_aq not in redacted
    assert redacted.count("[REDACTED]") == 2


def test_secret_redaction_does_not_redact_normal_text() -> None:
    normal_text = "AQ and AQUA and مشروعات ML scraping and project AQ.short"
    redacted = redact_secrets(normal_text)
    assert redacted == normal_text


def test_literal_secret_redaction_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from gigradar.core.logging import register_configured_secrets

    register_configured_secrets(
        [
            "SUPER_LITERAL_SECRET_VALUE_12345",
            "",
            "short",
            "your_gemini_api_key_here",
            "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        ]
    )

    text = (
        "Configured secret: SUPER_LITERAL_SECRET_VALUE_12345 and "
        "your_gemini_api_key_here and 123456789:ABCdefGHIjklMNOpqrsTUVwxyz and normal text"
    )
    redacted = redact_secrets(text)
    assert "SUPER_LITERAL_SECRET_VALUE_12345" not in redacted
    assert "[REDACTED]" in redacted
    # Known placeholders must NOT be redacted as literal secrets
    assert "your_gemini_api_key_here" in redacted
    assert "normal text" in redacted


def test_traceback_local_variables_not_shown_in_logs() -> None:
    import structlog
    from structlog.dev import ConsoleRenderer, RichTracebackFormatter

    from gigradar.core.logging import RedactingProcessorFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    formatter = RedactingProcessorFormatter(
        foreign_pre_chain=[],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            ConsoleRenderer(
                colors=False,
                exception_formatter=RichTracebackFormatter(
                    show_locals=False,
                    color_system="standard",
                ),
            ),
        ],
    )
    handler.setFormatter(formatter)
    test_logger = logging.getLogger("test_show_locals_logger")
    test_logger.handlers.clear()
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)

    def function_with_sensitive_local() -> None:
        fake_secret_token_in_frame = "".join(["DO_NOT_PRINT", "_LOCAL_FRAME", "_TOKEN_7777"])  # noqa: F841
        raise ValueError("Computation failed in worker frame")

    try:
        function_with_sensitive_local()
    except ValueError:
        test_logger.exception("Handled call error")

    output = stream.getvalue()
    assert "DO_NOT_PRINT_LOCAL_FRAME_TOKEN_7777" not in output
    assert "Computation failed in worker frame" in output


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
            await asyncio.sleep(0.005)
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
async def test_scheduler_setup_jobs_staggered(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_stagger.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    orch = PlatformOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)
    runner.setup_jobs(stagger_step_seconds=20.0)

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
async def test_scheduler_startup_health_checks_unhealthy_records_failure(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_health_fail.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    orch = MockOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)

    # Health check must never raise an unhandled error or crash
    results = await runner.startup_health_checks()
    assert recorded_failure is True
    assert all(status is False for status in results.values())

    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_startup_health_checks_healthy_and_exceptions(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_health_ok.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class MockClientHealthy:
        async def health_check(self) -> HealthReport:
            return HealthReport(platform_id="mock", is_healthy=True, message="OK")

        async def close(self) -> None:
            pass

    class MockClientRaising:
        async def health_check(self) -> HealthReport:
            raise ConnectionError("DNS resolution failed")

        async def close(self) -> None:
            pass

    class MixedOrchestrator(PlatformOrchestrator):
        def get_client(self, platform_name: str) -> Any:
            if platform_name == "mostaql":
                return MockClientHealthy()
            return MockClientRaising()

        async def record_startup_health_failure(
            self, platform_name: str, error_message: str
        ) -> None:
            pass

    orch = MixedOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)
    results = await runner.startup_health_checks()
    assert results.get("mostaql") is True
    assert results.get("khamsat") is False
    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_cleanup_interrupted_runs_with_active(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.repositories.scrape_run_repo import ScrapeRunRepository
    from gigradar.db.session import create_engine_from_url, get_async_session

    db_path = tmp_path / "cleanup_interrupted.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_async_session(engine=engine) as session:
        plat_repo = PlatformRepository(session)
        plat, _ = await plat_repo.get_or_create("mostaql", "https://mostaql.com")
        run_repo = ScrapeRunRepository(session)
        await run_repo.start_run(plat.id)
        await session.commit()

    orch = PlatformOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)
    count = await runner.cleanup_interrupted_runs()
    assert count >= 1
    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_run_once_success_and_disabled(tmp_path: Path) -> None:
    from unittest.mock import patch

    from gigradar.core.config_models import PlatformsConfig, PlatformSettings, PlatformThresholds
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_run_once.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class DummySuccessOrchestrator(PlatformOrchestrator):
        async def run_tick(
            self,
            platform_name: str,
            client: Any = None,
            session: Any = None,
            **kwargs: Any,
        ) -> TickResult:
            return TickResult(platform=platform_name, gigs_found=3, gigs_new=1, success=True)

    orch = DummySuccessOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)

    fake_cfg = PlatformsConfig(
        platforms={
            "enabled_p": PlatformSettings(
                name="Enabled",
                type="scraper",
                base_url="https://enabled.com",
                enabled=True,
                poll_interval_seconds=60,
                jitter_seconds_min=0,
                jitter_seconds_max=0,
                thresholds=PlatformThresholds(),
            ),
            "disabled_p": PlatformSettings(
                name="Disabled",
                type="scraper",
                base_url="https://disabled.com",
                enabled=False,
                poll_interval_seconds=60,
                jitter_seconds_min=0,
                jitter_seconds_max=0,
                thresholds=PlatformThresholds(),
            ),
        }
    )

    with patch("gigradar.pipeline.scheduler.load_platforms_config", return_value=fake_cfg):
        results = await runner.run_once()
        assert "enabled_p" in results
        assert results["enabled_p"].success is True
        assert "disabled_p" not in results

    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_setup_jobs_with_disabled_platform(tmp_path: Path) -> None:
    from unittest.mock import patch

    from gigradar.core.config_models import PlatformsConfig, PlatformSettings, PlatformThresholds
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_disabled.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    orch = PlatformOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)

    fake_cfg = PlatformsConfig(
        platforms={
            "plat_a": PlatformSettings(
                name="PlatA",
                type="scraper",
                base_url="https://plata.com",
                enabled=True,
                poll_interval_seconds=60,
                jitter_seconds_min=0,
                jitter_seconds_max=0,
                thresholds=PlatformThresholds(),
            ),
            "plat_b": PlatformSettings(
                name="PlatB",
                type="scraper",
                base_url="https://platb.com",
                enabled=False,
                poll_interval_seconds=60,
                jitter_seconds_min=0,
                jitter_seconds_max=0,
                thresholds=PlatformThresholds(),
            ),
        }
    )

    with patch("gigradar.pipeline.scheduler.load_platforms_config", return_value=fake_cfg):
        runner.setup_jobs(stagger_step_seconds=0.0)
        jobs = runner.scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert "poll_plat_a" in job_ids
        assert "poll_plat_b" not in job_ids

    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_run_forever_and_clean_shutdown(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_run_forever.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    fake_orch = FakeOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=fake_orch)

    shutdown_event = asyncio.Event()

    # Trigger shutdown after short delay
    async def trigger_shutdown() -> None:
        await asyncio.sleep(0.001)
        shutdown_event.set()

    shutdown_task = asyncio.create_task(trigger_shutdown())
    await runner.run_forever(shutdown_event=shutdown_event)
    await shutdown_task

    assert runner._is_running is False


@pytest.mark.asyncio
async def test_scheduler_run_once_with_exceptions(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_run_once_exc.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class FailingOrchestrator(PlatformOrchestrator):
        async def run_tick(
            self,
            platform_name: str,
            client: Any = None,
            session: Any = None,
            **kwargs: Any,
        ) -> TickResult:
            raise RuntimeError("Database unavailable")

    runner = SchedulerRunner(orchestrator=FailingOrchestrator(engine=engine))
    results = await runner.run_once()
    assert len(results) >= 2
    for _plat, res in results.items():
        assert res.success is False
        assert "Database unavailable" in str(res.error)
    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_platform_job_callback(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_callback.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    orch = MockOrchestrator(engine=engine)
    runner = SchedulerRunner(orchestrator=orch)
    runner.setup_jobs(stagger_step_seconds=0.0)

    # Invoke the registered job functions directly
    jobs = runner.scheduler.get_jobs()
    for job in jobs:
        await job.func()

    assert "mostaql" in calls
    assert "khamsat" in calls
    await runner.shutdown()


@pytest.mark.asyncio
async def test_scheduler_run_forever_cancelled_task(tmp_path: Path) -> None:
    from gigradar.db.models import Base
    from gigradar.db.session import create_engine_from_url

    db_path = tmp_path / "scheduler_cancelled.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

    runner = SchedulerRunner(orchestrator=DummyOrch(engine=engine))
    forever_task = asyncio.create_task(runner.run_forever())
    await asyncio.sleep(0.001)
    forever_task.cancel()
    await forever_task
    assert runner._is_running is False


def test_real_database_file_untouched_by_suite(guard_real_database: Any) -> None:
    from pathlib import Path

    db_path = Path("gigradar.db").resolve()
    current = (
        db_path.exists(),
        db_path.stat().st_size if db_path.exists() else 0,
        db_path.stat().st_mtime_ns if db_path.exists() else 0,
    )
    assert current == (
        guard_real_database.exists,
        guard_real_database.size,
        guard_real_database.mtime_ns,
    )

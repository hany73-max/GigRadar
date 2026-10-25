"""Tests for Typer CLI commands."""

import pytest
from typer.testing import CliRunner

import gigradar.core.settings as settings_module
from gigradar.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "GigRadar version" in result.stdout


def test_cli_doctor_offline() -> None:
    result = runner.invoke(app, ["doctor", "--offline"])
    assert result.exit_code == 0
    assert "GigRadar Doctor" in result.stdout
    assert "portfolio.yaml" in result.stdout
    assert "rules.yaml" in result.stdout
    assert "Platform Health Checks" in result.stdout
    assert "--offline passed" in result.stdout


def test_cli_doctor_detects_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    # Reset cached settings so env overrides are loaded
    monkeypatch.setattr(settings_module, "_settings", None)
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_ID", "123456789")

    result = runner.invoke(app, ["doctor", "--offline"])
    assert result.exit_code == 0
    assert "PLACEHOLDER" in result.stdout
    assert "Configured" not in result.stdout
    assert "your_gemini_api_key_here" in result.stdout

    # Clean up cached settings
    monkeypatch.setattr(settings_module, "_settings", None)


def test_cli_doctor_platform_health_checks_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    from gigradar.core.models import HealthReport

    class MockClient:
        async def health_check(self) -> HealthReport:
            return HealthReport(platform_id="mock", is_healthy=True, message="Mocked healthy")

        async def close(self) -> None:
            pass

    monkeypatch.setattr(
        "gigradar.pipeline.orchestrator.PlatformOrchestrator.get_client",
        lambda self, name: MockClient(),
    )
    result = runner.invoke(app, ["doctor", "--skip-live-llm"])
    assert result.exit_code == 0
    assert "Platform Health Checks" in result.stdout
    assert "Mocked healthy" in result.stdout


def test_cli_scrape_once_unsupported_platform() -> None:
    result = runner.invoke(app, ["scrape-once", "unknown_platform"])
    assert result.exit_code == 1
    assert "Unsupported platform" in result.stdout


def test_cli_scrape_once_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    import gigradar.cli as cli_module
    from gigradar.core.models import Gig

    sample_gig = Gig(
        platform_id="mostaql",
        external_id="123456",
        url="https://mostaql.com/project/123456",
        title="بناء نموذج تعلم آلي",
        description="تفاصيل المشروع",
        budget_min=100.0,
        budget_max=250.0,
        currency="USD",
        bids_count=5,
        posted_at=None,
        client_name="Test Client",
        language="ar",
    )

    async def mock_run_scrape_once(
        platform_name: str, limit: int, fetch_details: bool, all_gigs: bool = False
    ) -> list[Gig]:
        return [sample_gig]

    monkeypatch.setattr(cli_module, "_run_scrape_once", mock_run_scrape_once)

    result = runner.invoke(app, ["scrape-once", "mostaql", "--limit", "1"])
    assert result.exit_code == 0
    assert "123456" in result.stdout
    assert "Mostaql" in result.stdout
    assert "$100 - $250" in result.stdout


def test_cli_scrape_once_bids_count_none_displays_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    import gigradar.cli as cli_module
    from gigradar.core.models import Gig

    sample_gig = Gig(
        platform_id="khamsat",
        external_id="799121",
        url="https://khamsat.com/community/requests/799121",
        title="طلب خدمة غير موجودة",
        description="تفاصيل الطلب",
        budget_min=None,
        budget_max=None,
        currency="USD",
        bids_count=None,
        posted_at=None,
        client_name="Test Buyer",
        language="ar",
    )

    async def mock_run_scrape_once(
        platform_name: str, limit: int, fetch_details: bool, all_gigs: bool = False
    ) -> list[Gig]:
        return [sample_gig]

    monkeypatch.setattr(cli_module, "_run_scrape_once", mock_run_scrape_once)

    result = runner.invoke(app, ["scrape-once", "khamsat", "--limit", "1"])
    assert result.exit_code == 0
    assert "799121" in result.stdout
    assert "Khamsat" in result.stdout
    assert "-" in result.stdout


def test_cli_scrape_once_freelancer(monkeypatch: pytest.MonkeyPatch) -> None:
    import gigradar.cli as cli_module
    from gigradar.core.models import Gig

    freelancer_gig = Gig(
        platform_id="freelancer",
        external_id="40773380",
        url="https://www.freelancer.com/projects/40773380",
        title="Extract App Photos",
        description="Extract photos from app",
        budget_min=10.0,
        budget_max=20.0,
        currency="GBP",
        budget_min_usd=13.33,
        budget_max_usd=26.66,
        budget_usd_est=20.0,
        bids_count=31,
        posted_at=None,
        client_name=None,
        language="en",
        project_type="fixed",
    )

    async def mock_run_scrape_once(
        platform_name: str, limit: int, fetch_details: bool, all_gigs: bool = False
    ) -> list[Gig]:
        return [freelancer_gig]

    monkeypatch.setattr(cli_module, "_run_scrape_once", mock_run_scrape_once)

    result = runner.invoke(app, ["scrape-once", "freelancer", "--limit", "1"])
    assert result.exit_code == 0
    assert "40773380" in result.stdout
    assert "Freelancer" in result.stdout
    assert "GBP 10 - 20" in result.stdout
    assert "(~$13-$27)" in result.stdout
    assert "31" in result.stdout

    # Test --all flag
    result_all = runner.invoke(app, ["scrape-once", "freelancer", "--limit", "1", "--all"])
    assert result_all.exit_code == 0
    assert "40773380" in result_all.stdout


def test_cli_classify_stored_and_rules_report() -> None:
    """Test classify-stored, rules-report, and explain-gig end-to-end against isolated DB."""
    import asyncio

    from gigradar.db.models import Gig, utc_now
    from gigradar.db.repositories.platform_repo import PlatformRepository
    from gigradar.db.session import get_async_session

    async def _seed_data() -> None:
        async with get_async_session() as session:
            p_repo = PlatformRepository(session)
            plat_mostaql, _ = await p_repo.get_or_create("mostaql", "https://mostaql.com")
            plat_khamsat, _ = await p_repo.get_or_create("khamsat", "https://khamsat.com")

            # 1. Pass gig (ML)
            gig_pass = Gig(
                platform_id=plat_mostaql.id,
                external_id="11111",
                url="https://mostaql.com/project/11111",
                title="تدريب نموذج تصنيف بيانات باستخدام scikit-learn",
                description="مشروع تعلم آلي متقدم",
                budget_max_usd=100.0,
                bids_count=5,
                posted_at=utc_now(),
                detail_level="full",
                processing_state="detail_fetched",
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
            )
            # 2. Reject gig (Academic)
            gig_reject = Gig(
                platform_id=plat_mostaql.id,
                external_id="22222",
                url="https://mostaql.com/project/22222",
                title="حل واجب جامعي لمادة بايثون",
                description="واجب منزلي",
                budget_max_usd=50.0,
                bids_count=2,
                posted_at=utc_now(),
                detail_level="full",
                processing_state="detail_fetched",
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
            )
            # 3. Khamsat title-only pass
            gig_khamsat = Gig(
                platform_id=plat_khamsat.id,
                external_id="33333",
                url="https://khamsat.com/message/33333",
                title="خوارزمية ذكاء اصطناعي وتحليل بيانات",
                description=None,
                budget_max_usd=None,
                bids_count=None,
                posted_at=utc_now(),
                detail_level="title_only",
                processing_state="detail_fetched",
                first_seen_at=utc_now(),
                last_seen_at=utc_now(),
            )
            session.add_all([gig_pass, gig_reject, gig_khamsat])
            await session.commit()

    asyncio.run(_seed_data())

    # 1. Test classify-stored
    res_classify = runner.invoke(app, ["classify-stored"])
    assert res_classify.exit_code == 0
    assert "Stage 1 Rules Classifier" in res_classify.stdout
    assert "PASS" in res_classify.stdout
    assert "REJECT" in res_classify.stdout
    assert "11111" in res_classify.stdout
    assert "22222" in res_classify.stdout
    assert "33333" in res_classify.stdout
    assert "Passed: 2" in res_classify.stdout
    assert "Rejected: 1" in res_classify.stdout

    # 2. Test classify-stored with --reclassify
    res_reclassify = runner.invoke(app, ["classify-stored", "--reclassify"])
    assert res_reclassify.exit_code == 0
    assert "Classification Complete" in res_reclassify.stdout

    # 3. Test rules-report
    res_report = runner.invoke(app, ["rules-report"])
    assert res_report.exit_code == 0
    assert "Stage 1 Rules Classification Report" in res_report.stdout
    assert "Platform Pass / Reject Rates" in res_report.stdout
    assert "mostaql" in res_report.stdout
    assert "khamsat" in res_report.stdout
    assert "Top 10 Reject Reasons Overall" in res_report.stdout
    assert "ALL Passed Gigs" in res_report.stdout

    # 4. Test explain-gig
    res_explain = runner.invoke(app, ["explain-gig", "mostaql", "11111"])
    assert res_explain.exit_code == 0
    assert "Gig Rules Explanation" in res_explain.stdout
    assert "11111" in res_explain.stdout
    assert "PASSED Stage 1 Rules Filter" in res_explain.stdout
    assert "include:ml_dl:" in res_explain.stdout

    # 5. Test explain-gig for reject
    res_explain_rej = runner.invoke(app, ["explain-gig", "mostaql", "22222"])
    assert res_explain_rej.exit_code == 0
    assert "REJECTED" in res_explain_rej.stdout
    assert "hard_reject:academic" in res_explain_rej.stdout

    # 6. Test explain-gig non-existent
    res_explain_404 = runner.invoke(app, ["explain-gig", "mostaql", "999999"])
    assert res_explain_404.exit_code == 1
    assert "not found" in res_explain_404.stdout

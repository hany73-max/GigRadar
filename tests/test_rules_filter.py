"""Comprehensive test suite for Stage 1 deterministic rules filter.

Covers:
- Golden dataset execution across all 44 test cases in tests/golden/rules_cases.yaml
- Arabic normalization details (tashkeel, tatweel, alef variants, ya, ta marbuta, digits)
- Arabic clitic prefixes (و, ف, ب, ل, ك, ال, لل, وال, بال, كال, فال)
- Latin word boundaries ("Java" vs "JavaScript")
- Budget logic (fixed range max, hourly min rate, unknown budget)
- Bids logic (bids limit, unknown bids)
- Khamsat title-only handling
- Ambiguous words passing to Stage 2 with hints
- Category rules (weak signal: include hits override category deny)
- Database repository classification persistence and stale protection
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from gigradar.classify.normalize import compile_keyword_pattern, normalize_text
from gigradar.classify.rules_filter import RuleResult, RulesFilter
from gigradar.db.models import Gig, utc_now
from gigradar.db.repositories.gig_repo import GigRepository
from gigradar.db.repositories.platform_repo import PlatformRepository


@dataclass
class MockGig:
    """Mock gig structure for unit testing the rules filter."""

    title: str
    description: str | None = None
    platform_id: str = "mostaql"
    detail_level: str = "full"
    project_type: str = "fixed"
    budget_max_usd: float | None = 100.0
    budget_usd_est: float | None = None
    bids_count: int | None = 5
    posted_at: datetime | None = None
    category_raw: str | None = None
    tags_raw: list[str] | None = None


# ------------------------------------------------------------------------------
# 1. Golden Dataset Test
# ------------------------------------------------------------------------------
def test_golden_rules_cases() -> None:
    """Run all test cases from tests/golden/rules_cases.yaml through RulesFilter."""
    golden_path = Path("tests/golden/rules_cases.yaml")
    assert golden_path.exists(), f"Golden file not found at {golden_path}"

    with golden_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cases = data.get("cases", [])
    assert len(cases) >= 40, f"Expected at least 40 cases, got {len(cases)}"

    rules_filter = RulesFilter()

    failures: list[str] = []

    for case in cases:
        case_id = case["id"]
        gig = MockGig(
            title=case["title"],
            description=case.get("description"),
            platform_id=case.get("platform", "mostaql"),
            detail_level=case.get("detail_level", "full"),
            project_type=case.get("project_type", "fixed"),
            budget_max_usd=case.get("budget_max_usd", 100.0),
            bids_count=case.get("bids_count", 5),
            posted_at=datetime.now(UTC),
            category_raw=case.get("category_raw"),
        )

        res: RuleResult = rules_filter.evaluate(gig, platform_name=gig.platform_id)
        expected_passed: bool = case["expected_passed"]

        if res.passed != expected_passed:
            failures.append(
                f"Case '{case_id}' failed pass check: expected passed={expected_passed}, "
                f"got {res.passed} (reason: {res.reject_reason}, hits: {res.hits})"
            )
            continue

        # Check reason prefix if expected
        expected_reason = case.get("expected_reason_prefix")
        if expected_reason and not res.passed:
            actual_reason = res.reject_reason or ""
            if not actual_reason.startswith(expected_reason):
                failures.append(
                    f"Case '{case_id}' reason mismatch: expected '{expected_reason}', "
                    f"got '{actual_reason}' (hits: {res.hits})"
                )

        # Check expected flags if specified
        expected_flags = case.get("expected_flags")
        if expected_flags:
            for flag in expected_flags:
                if flag not in res.flags:
                    failures.append(
                        f"Case '{case_id}' missing expected flag '{flag}', got {res.flags}"
                    )

    assert not failures, "\n".join(failures)


# ------------------------------------------------------------------------------
# 2. Arabic Normalization Unit Tests
# ------------------------------------------------------------------------------
def test_arabic_normalization_tashkeel_and_tatweel() -> None:
    # Tashkeel removal
    raw = "تَعَلُّمُ الآلَةِ وَالذَّكَاءُ الاصْطِنَاعِيُّ"
    normalized = normalize_text(raw)
    assert normalized == "تعلم الاله والذكاء الاصطناعي"

    # Tatweel removal
    tatweel_text = "تـــصـــنـــيـــف"
    assert normalize_text(tatweel_text) == "تصنيف"


def test_arabic_normalization_alef_variants() -> None:
    assert normalize_text("أحمد") == "احمد"
    assert normalize_text("إبراهيم") == "ابراهيم"
    assert normalize_text("آلة") == "اله"
    assert normalize_text("ٱستخراج") == "استخراج"


def test_arabic_normalization_ya_and_ta_marbuta() -> None:
    # Alef maqsura to ya
    assert normalize_text("على مستوى") == "علي مستوي"
    # Ta marbuta to ha
    assert normalize_text("شبكة عصبية عميقة") == "شبكه عصبيه عميقه"


def test_arabic_indic_digits_translation() -> None:
    raw = "ميزانية قدرها ٥٠٠ دولار في ٣ أيام"
    norm = normalize_text(raw)
    assert "500" in norm
    assert "3" in norm


# ------------------------------------------------------------------------------
# 3. Arabic Clitic Prefixes Tests
# ------------------------------------------------------------------------------
def test_arabic_clitic_prefixes() -> None:
    # Keyword: "تصنيف"
    pattern = compile_keyword_pattern("تصنيف")
    assert pattern.search("مشروع تصنيف بيانات")
    assert pattern.search("خوارزمية للتصنيف الآلي")
    assert pattern.search("والتصنيف هو المطلوب")
    assert pattern.search("يقوم بالتصنيف بدقة")
    assert pattern.search("كاللتصنيف") or pattern.search("كالتصنيف")
    assert pattern.search("فالتصنيف ممتاز")

    # Keyword: "ذكاء اصطناعي"
    pattern_ai = compile_keyword_pattern("ذكاء اصطناعي")
    assert pattern_ai.search("مشروع ذكاء اصطناعي")
    assert pattern_ai.search("مشروع الذكاء الاصطناعي")
    assert pattern_ai.search("بالذكاء الاصطناعي الحديث")
    assert pattern_ai.search("والذكاء الاصطناعي المتطور")
    assert pattern_ai.search("للذكاء الاصطناعي دور هام")


# ------------------------------------------------------------------------------
# 4. Strict Latin Word Boundaries Tests
# ------------------------------------------------------------------------------
def test_strict_latin_boundaries() -> None:
    pattern_java = compile_keyword_pattern("Java")
    assert pattern_java.search("Need a Java developer for backend")
    assert pattern_java.search("Java, Spring Boot, and SQL")
    # Must NOT match JavaScript or JavaApp
    assert not pattern_java.search("Need a JavaScript developer")
    assert not pattern_java.search("JavaApp is crashing")
    assert not pattern_java.search("my_java_code")

    pattern_py = compile_keyword_pattern("py")
    assert not pattern_py.search("python developer needed")


# ------------------------------------------------------------------------------
# 5. Budget & Threshold Edge Cases
# ------------------------------------------------------------------------------
def test_budget_fixed_range_max() -> None:
    """Fixed-price gigs use budget_max_usd for minimum budget comparison."""
    rules_filter = RulesFilter()

    # Range $10 - $500: min is $10 (< $25), but max is $500 (>= $25) -> must PASS
    gig = MockGig(
        title="Python web scraping for competitor prices",
        project_type="fixed",
        budget_max_usd=500.0,
    )
    res = rules_filter.evaluate(gig)
    assert res.passed
    assert any("budget_ok" in h for h in res.hits)


def test_budget_hourly_vs_min_hourly_rate() -> None:
    rules_filter = RulesFilter()

    # Hourly at $20/hr >= $15 min_hourly_rate_usd -> PASS
    gig_pass = MockGig(
        title="FastAPI deploy model engineer",
        project_type="hourly",
        budget_max_usd=20.0,
    )
    res_pass = rules_filter.evaluate(gig_pass)
    assert res_pass.passed

    # Hourly at $10/hr < $15 min_hourly_rate_usd -> REJECT
    gig_reject = MockGig(
        title="FastAPI deploy model engineer",
        project_type="hourly",
        budget_max_usd=10.0,
    )
    res_reject = rules_filter.evaluate(gig_reject)
    assert not res_reject.passed
    assert "hourly_rate_below_min" in (res_reject.reject_reason or "")


def test_budget_unknown_and_bids_unknown_pass() -> None:
    rules_filter = RulesFilter()

    # Unknown budget and unknown bids must PASS
    gig = MockGig(
        title="Machine learning computer vision model development",
        budget_max_usd=None,
        budget_usd_est=None,
        bids_count=None,
    )
    res = rules_filter.evaluate(gig)
    assert res.passed
    assert "budget:unknown_passed" in res.hits
    assert "bids:unknown_passed" in res.hits


# ------------------------------------------------------------------------------
# 6. Detail Level = title_only (Khamsat)
# ------------------------------------------------------------------------------
def test_title_only_khamsat_evaluation() -> None:
    rules_filter = RulesFilter()

    # Evaluates title only without penalizing missing description
    gig = MockGig(
        title="تدريب نموذج تعلم آلي لتصنيف المستندات",
        description=None,
        detail_level="title_only",
        platform_id="khamsat",
    )
    res = rules_filter.evaluate(gig)
    assert res.passed
    assert "detail_level:title_only" in res.hits


# ------------------------------------------------------------------------------
# 7. Category Weak Signal: Include Keywords Override Category Deny
# ------------------------------------------------------------------------------
def test_category_deny_overridden_by_include_keyword() -> None:
    rules_filter = RulesFilter()

    # Client misfiled ML project under "Design & Graphics" category
    gig = MockGig(
        title="تدريب شبكة عصبية CNN لتصنيف الصور الطبية",
        description="استخدام PyTorch لتدريب نموذج تصنيف صور عالي الدقة.",
        category_raw="Design & Graphics",
    )
    res = rules_filter.evaluate(gig)
    assert res.passed
    assert any("category_deny_overridden" in h for h in res.hits)


def test_category_denied_when_no_include_keywords() -> None:
    rules_filter = RulesFilter()

    # Gig has no include keywords AND is in deny category
    gig = MockGig(
        title="تصميم بوستر لحملة تسويقية",
        description="نريد تصميم جذاب ومميز للطباعة والنشر على منصات التواصل.",
        category_raw="Design & Graphics",
    )
    res = rules_filter.evaluate(gig)
    assert not res.passed
    assert "category_denied" in (res.reject_reason or "")


# ------------------------------------------------------------------------------
# 8. Ambiguous Keywords Pass to Stage 2 with Flags
# ------------------------------------------------------------------------------
def test_ambiguous_words_pass_with_flags() -> None:
    rules_filter = RulesFilter()

    # "نموذج"
    res_model = rules_filter.evaluate(
        MockGig(title="تصميم نموذج متابعة الأداء في إكسل", description="نموذج بسيط")
    )
    assert res_model.passed
    assert "ambiguous_ml_model" in res_model.flags

    # "تدريب"
    res_training = rules_filter.evaluate(
        MockGig(title="تدريب فريق المبيعات على مهارات التواصل", description="دورة تدريب")
    )
    assert res_training.passed
    assert "ambiguous_training" in res_training.flags

    # "chatbot"
    res_bot = rules_filter.evaluate(
        MockGig(title="ربط chatbot للرد على استفسارات الزبائن", description="شات بوت ذكي")
    )
    assert res_bot.passed
    assert "likely_llm_wrapper" in res_bot.flags


# ------------------------------------------------------------------------------
# 9. Database Repository Classification & Provenance Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_classification_db_persistence_and_stale_protection() -> None:
    """Verify that recording classifications appends rows and respects stale state invariant."""
    from gigradar.db.session import get_async_session

    async with get_async_session() as test_session:
        platform_repo = PlatformRepository(test_session)
        gig_repo = GigRepository(test_session)

        plat, _ = await platform_repo.get_or_create("testplat", "https://example.com")
        await test_session.commit()

        # 1. Normal fresh gig
        gig = Gig(
            platform_id=plat.id,
            external_id="ext_fresh_1",
            url="https://example.com/1",
            title="Build ML model with scikit-learn",
            description="Classification task",
            detail_level="full",
            processing_state="detail_fetched",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        test_session.add(gig)
        await test_session.commit()

        # Classify as passed
        updated_gig, cls_1 = await gig_repo.record_classification(
            gig_id=gig.id,
            stage="rules",
            passed=True,
            rule_hits=["include:ml_dl:scikit-learn"],
            rules_version="v_test1",
        )
        await test_session.commit()

        assert updated_gig.processing_state == "rules_passed"
        assert cls_1.stage == "rules"
        assert cls_1.passed is True
        assert cls_1.rules_version == "v_test1"

        # Reclassify with newer version (appends row, does not delete previous)
        _, cls_2 = await gig_repo.record_classification(
            gig_id=gig.id,
            stage="rules",
            passed=False,
            rule_hits=["hard_reject:academic"],
            reject_reason="hard_reject:academic",
            rules_version="v_test2",
        )
        await test_session.commit()

        assert updated_gig.processing_state == "rules_rejected"
        assert cls_2.rules_version == "v_test2"

        latest = await gig_repo.get_latest_classification(gig.id, stage="rules")
        assert latest is not None
        assert latest.id == cls_2.id
        assert latest.passed is False

        # 2. Stale gig invariant test:
        # A stale gig's processing_state must NEVER be overwritten to rules_passed/rules_rejected!
        stale_gig = Gig(
            platform_id=plat.id,
            external_id="ext_stale_1",
            url="https://example.com/stale",
            title="Old gig",
            detail_level="full",
            processing_state="stale",
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        )
        test_session.add(stale_gig)
        await test_session.commit()

        classified_stale, _ = await gig_repo.record_classification(
            gig_id=stale_gig.id,
            stage="rules",
            passed=True,
            rule_hits=["include:ml_dl:pytorch"],
            rules_version="v_test1",
        )
        await test_session.commit()

        # Invariant: state MUST remain 'stale'
        assert classified_stale.processing_state == "stale"

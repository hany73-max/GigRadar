"""Table-driven unit tests for platform normalization helpers."""

from datetime import UTC, datetime

import pytest

from gigradar.platforms.common.normalization import (
    detect_language,
    format_budget_display,
    normalize_digits,
    parse_bids_count,
    parse_budget_range,
    parse_datetime_or_relative,
    parse_relative_arabic_time,
)


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("١٢٣٤٥", "12345"),
        ("۰۱۲۳۴۵۶۷۸۹", "0123456789"),
        ("الميزانية: ٥٠٫٠٠$", "الميزانية: 50.00$"),
        ("1,000،20", "1,000,20"),
        ("لا توجد أرقام", "لا توجد أرقام"),
        ("", ""),
    ],
)
def test_normalize_digits(input_str: str, expected: str) -> None:
    assert normalize_digits(input_str) == expected


@pytest.mark.parametrize(
    ("text", "expected_seconds_ago"),
    [
        ("الآن", 0),
        ("منذ لحظات", 0),
        ("منذ ثانية", 1),
        ("منذ ثانيتين", 2),
        ("منذ 30 ثانية", 30),
        ("منذ 15 ثواني", 15),
        ("منذ دقيقة", 60),
        ("منذ دقيقتين", 120),
        ("منذ 10 دقائق", 600),
        ("منذ ١٥ دقيقة", 900),
        ("منذ ساعة", 3600),
        ("منذ ساعتين", 7200),
        ("منذ 3 ساعات", 10800),
        ("منذ 8 ساعات و5 دقائق", 29100),
        ("منذ يوم", 86400),
        ("منذ يومين", 172800),
        ("منذ 3 أيام", 259200),
        ("منذ أسبوع", 7 * 86400),
        ("منذ أسبوعين", 14 * 86400),
        ("منذ 5 أسابيع", 35 * 86400),
        ("منذ شهر", 30 * 86400),
        ("منذ شهرين", 60 * 86400),
        ("منذ سنة", 365 * 86400),
    ],
)
def test_parse_relative_arabic_time(text: str, expected_seconds_ago: int) -> None:
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    result = parse_relative_arabic_time(text, base_time=base)
    actual_diff = (base - result).total_seconds()
    assert abs(actual_diff - expected_seconds_ago) < 2


@pytest.mark.parametrize(
    "invalid_text",
    [
        "garbage string",
        "غير محدد",
        "foo 123 bar",
        "",
        "   ",
    ],
)
def test_parse_relative_arabic_time_raises_on_unrecognized(invalid_text: str) -> None:
    with pytest.raises(ValueError):
        parse_relative_arabic_time(invalid_text)


@pytest.mark.parametrize(
    ("text", "attr", "expected_iso"),
    [
        ("", "2026-10-17 17:14:28", "2026-10-17T17:14:28+00:00"),
        ("", "17/10/2026 17:03:28 GMT", "2026-10-17T17:03:28+00:00"),
        ("منذ 10 دقائق", None, "2026-10-17T11:50:00+00:00"),
        ("منذ 5 أسابيع", None, "2026-09-12T12:00:00+00:00"),
    ],
)
def test_parse_datetime_or_relative(text: str, attr: str | None, expected_iso: str) -> None:
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    result = parse_datetime_or_relative(text, datetime_attr=attr, base_time=base)
    assert result is not None
    assert result.isoformat() == expected_iso


def test_parse_datetime_or_relative_unrecognized_returns_none() -> None:
    assert parse_datetime_or_relative("garbage string", datetime_attr=None) is None


@pytest.mark.parametrize(
    ("text", "expected_min", "expected_max", "expected_curr"),
    [
        ("$50.00 - $100.00", 50.0, 100.0, "USD"),
        ("$25.00 - $50.00", 25.0, 50.0, "USD"),
        ("$25", 25.0, 25.0, "USD"),
        ("100$ - 250$", 100.0, 250.0, "USD"),
        ("الميزانية: $1,000.00 - $2,500.00", 1000.0, 2500.0, "USD"),
        ("500 ريال", 500.0, 500.0, "SAR"),
        ("غير محدد", None, None, "USD"),
        ("", None, None, "USD"),
    ],
)
def test_parse_budget_range(
    text: str,
    expected_min: float | None,
    expected_max: float | None,
    expected_curr: str,
) -> None:
    b_min, b_max, curr = parse_budget_range(text)
    assert b_min == expected_min
    assert b_max == expected_max
    assert curr == expected_curr


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("أضف أول عرض", 0),
        ("عرض واحد", 1),
        ("عرضين", 2),
        ("14 عرض", 14),
        ("١٥ عرض", 15),
        ("25 عروض", 25),
        ("", 0),
    ],
)
def test_parse_bids_count(text: str, expected: int) -> None:
    assert parse_bids_count(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("مطلوب نموذج تعلم آلي لتصنيف الصور الطبية بدقة عالية", "ar"),
        ("Looking for an experienced Python developer to build a machine learning model", "en"),
        (
            "مطلوب مهندس ذكاء اصطناعي لبناء Machine Learning pipeline باستخدام PyTorch و FastAPI",
            "mixed",
        ),
        ("", "ar"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 1. Fixed range (USD)
        (
            {"budget_min": 100.0, "budget_max": 250.0, "currency": "USD", "project_type": "fixed"},
            "$100 - $250",
        ),
        # 2. Single value (USD)
        (
            {"budget_min": 100.0, "budget_max": None, "currency": "USD", "project_type": "fixed"},
            "$100",
        ),
        # 3. Non-USD range
        (
            {
                "budget_min": 150.0,
                "budget_max": 220.0,
                "currency": "EUR",
                "budget_min_usd": 168.0,
                "budget_max_usd": 247.0,
                "project_type": "fixed",
            },
            "EUR 150 - 220 (~$168-$247)",
        ),
        # 4. Hourly (USD)
        (
            {"budget_min": 8.0, "budget_max": 15.0, "currency": "USD", "project_type": "hourly"},
            "$8-$15/hr",
        ),
        # 5. Hourly (non-USD range)
        (
            {
                "budget_min": 1500.0,
                "budget_max": 3500.0,
                "currency": "INR",
                "budget_min_usd": 15.8,
                "budget_max_usd": 36.86,
                "project_type": "hourly",
            },
            "INR 1500 - 3500/hr (~$16-$37/hr)",
        ),
        # 6. Missing budget
        (
            {"budget_min": None, "budget_max": None, "currency": "USD", "project_type": "fixed"},
            "-",
        ),
    ],
)
def test_format_budget_display(kwargs: dict[str, object], expected: str) -> None:
    assert format_budget_display(**kwargs) == expected  # type: ignore[arg-type]

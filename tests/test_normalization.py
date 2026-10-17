"""Table-driven unit tests for platform normalization helpers."""

from datetime import UTC, datetime

import pytest

from gigradar.platforms.common.normalization import (
    detect_language,
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
    ("text", "expected_minutes_ago"),
    [
        ("منذ دقيقة", 1),
        ("منذ دقيقتين", 2),
        ("منذ 10 دقائق", 10),
        ("منذ ١٥ دقيقة", 15),
        ("منذ ساعة", 60),
        ("منذ ساعتين", 120),
        ("منذ 3 ساعات", 180),
        ("منذ 8 ساعات و5 دقائق", 485),
        ("منذ يوم", 1440),
        ("منذ يومين", 2880),
        ("الآن", 0),
        ("منذ لحظات", 0),
    ],
)
def test_parse_relative_arabic_time(text: str, expected_minutes_ago: int) -> None:
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    result = parse_relative_arabic_time(text, base_time=base)
    expected_seconds = expected_minutes_ago * 60
    actual_diff = (base - result).total_seconds()
    assert abs(actual_diff - expected_seconds) < 2


@pytest.mark.parametrize(
    ("text", "attr", "expected_iso"),
    [
        ("", "2026-10-17 17:14:28", "2026-10-17T17:14:28+00:00"),
        ("", "17/10/2026 17:03:28 GMT", "2026-10-17T17:03:28+00:00"),
        ("منذ 10 دقائق", None, "2026-10-17T11:50:00+00:00"),
    ],
)
def test_parse_datetime_or_relative(text: str, attr: str | None, expected_iso: str) -> None:
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    result = parse_datetime_or_relative(text, datetime_attr=attr, base_time=base)
    assert result is not None
    assert result.isoformat() == expected_iso


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

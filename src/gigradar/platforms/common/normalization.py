"""Normalization helpers for Arabic-Indic digits, relative dates, budgets, and language detection."""

import re
from datetime import UTC, datetime, timedelta
from typing import Literal

# Translation table for Arabic-Indic and Eastern Arabic-Indic numerals
ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EASTERN_ARABIC_INDIC_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ASCII_DIGITS = "0123456789"

DIGIT_TRANSLATION_TABLE = str.maketrans(
    ARABIC_INDIC_DIGITS + EASTERN_ARABIC_INDIC_DIGITS,
    ASCII_DIGITS + ASCII_DIGITS,
)


def normalize_digits(text: str) -> str:
    """Translate Arabic-Indic digits to ASCII and normalize common Arabic punctuation."""
    if not text:
        return ""
    translated = text.translate(DIGIT_TRANSLATION_TABLE)
    # Normalize Arabic decimal separator (U+066B) to standard dot
    translated = translated.replace("٫", ".")
    # Normalize Arabic comma (U+060C) to standard comma
    translated = translated.replace("،", ",")
    return translated


def parse_relative_arabic_time(text: str, base_time: datetime | None = None) -> datetime:
    """Parse relative Arabic time expressions (e.g., 'منذ 10 دقائق', 'منذ 8 ساعات و5 دقائق') into UTC datetime."""
    now = base_time or datetime.now(UTC)
    if not text:
        return now

    cleaned = normalize_digits(text.strip().lower())

    # Fast check for immediate time
    if any(k in cleaned for k in ["الآن", "لحظات", "ثوان", "أقل من دقيقة", "اقل من دقيقة"]):
        return now

    total_delta = timedelta()

    # Days
    days_match = re.search(r"(\d+)\s*(?:يوم|أيام|ايام)", cleaned)
    if days_match:
        total_delta += timedelta(days=int(days_match.group(1)))
    elif "يومين" in cleaned:
        total_delta += timedelta(days=2)
    elif "يوم" in cleaned:
        total_delta += timedelta(days=1)

    # Hours
    hours_match = re.search(r"(\d+)\s*(?:ساعة|ساعات)", cleaned)
    if hours_match:
        total_delta += timedelta(hours=int(hours_match.group(1)))
    elif "ساعتين" in cleaned:
        total_delta += timedelta(hours=2)
    elif "ساعة" in cleaned:
        total_delta += timedelta(hours=1)

    # Minutes
    minutes_match = re.search(r"(\d+)\s*(?:دقيقة|دقائق)", cleaned)
    if minutes_match:
        total_delta += timedelta(minutes=int(minutes_match.group(1)))
    elif "دقيقتين" in cleaned:
        total_delta += timedelta(minutes=2)
    elif "دقيقة" in cleaned:
        total_delta += timedelta(minutes=1)

    # Months (approx 30 days)
    months_match = re.search(r"(\d+)\s*(?:شهر|أشهر|اشهر)", cleaned)
    if months_match:
        total_delta += timedelta(days=int(months_match.group(1)) * 30)
    elif "شهرين" in cleaned:
        total_delta += timedelta(days=60)
    elif "شهر" in cleaned:
        total_delta += timedelta(days=30)

    # Years (approx 365 days)
    years_match = re.search(r"(\d+)\s*(?:سنة|سنوات|عام|أعوام)", cleaned)
    if years_match:
        total_delta += timedelta(days=int(years_match.group(1)) * 365)
    elif "سنتين" in cleaned or "عامين" in cleaned:
        total_delta += timedelta(days=730)
    elif "سنة" in cleaned or "عام" in cleaned:
        total_delta += timedelta(days=365)

    return now - total_delta


def parse_datetime_or_relative(
    text: str,
    datetime_attr: str | None = None,
    base_time: datetime | None = None,
) -> datetime | None:
    """Parse machine-readable timestamp (HTML attribute) or fall back to Arabic relative time."""
    if datetime_attr:
        clean_attr = datetime_attr.strip()
        # Format 1: Mostaql standard 'YYYY-MM-DD HH:MM:SS'
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(clean_attr, fmt)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                pass

        # Format 2: Khamsat standard 'DD/MM/YYYY HH:MM:SS GMT'
        if "GMT" in clean_attr:
            clean_gmt = clean_attr.replace("GMT", "").strip()
            for fmt in (
                "%d/%m/%Y %H:%M:%S",
                "%d-%m-%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
            ):
                try:
                    dt = datetime.strptime(clean_gmt, fmt)
                    return dt.replace(tzinfo=UTC)
                except ValueError:
                    pass

    if text:
        return parse_relative_arabic_time(text, base_time=base_time)

    return None


def parse_budget_range(text: str) -> tuple[float | None, float | None, str]:
    """Parse budget range and currency from platform budget string.

    Examples:
        '$50.00 - $100.00' -> (50.0, 100.0, 'USD')
        '$25' -> (25.0, 25.0, 'USD')
        '100$ - 200$' -> (100.0, 200.0, 'USD')
    """
    if not text:
        return None, None, "USD"

    normalized = normalize_digits(text)
    # Remove thousand separators inside numbers
    cleaned = re.sub(r"(\d),(\d{3})", r"\1\2", normalized)

    # Detect currency symbol
    currency = "USD"
    if "دولار" in cleaned or "$" in cleaned:
        currency = "USD"
    elif "ريال" in cleaned or "SAR" in cleaned:
        currency = "SAR"
    elif "جنيه" in cleaned or "EGP" in cleaned:
        currency = "EGP"

    # Extract all numbers
    numbers = [float(m) for m in re.findall(r"\d+(?:\.\d+)?", cleaned)]

    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1]), currency
    if len(numbers) == 1:
        return numbers[0], numbers[0], currency

    return None, None, currency


def parse_bids_count(text: str) -> int:
    """Extract bid count from text.

    Examples:
        'أضف أول عرض' -> 0
        'عرض واحد' -> 1
        'عرضين' -> 2
        '14 عرض' -> 14
    """
    if not text:
        return 0

    normalized = normalize_digits(text.strip())

    if "أول عرض" in normalized or "اول عرض" in normalized:
        return 0
    if "عرض واحد" in normalized:
        return 1
    if "عرضين" in normalized or "عرضان" in normalized:
        return 2

    match = re.search(r"(\d+)", normalized)
    if match:
        return int(match.group(1))

    return 0


def detect_language(text: str) -> Literal["ar", "en", "mixed"]:
    """Detect whether text is predominantly Arabic ('ar'), English ('en'), or 'mixed'."""
    if not text:
        return "ar"

    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]", text))
    latin_chars = len(re.findall(r"[a-zA-Z]", text))

    total = arabic_chars + latin_chars
    if total == 0:
        return "ar"

    arabic_ratio = arabic_chars / total
    latin_ratio = latin_chars / total

    if arabic_ratio >= 0.70:
        return "ar"
    if latin_ratio >= 0.70:
        return "en"
    return "mixed"

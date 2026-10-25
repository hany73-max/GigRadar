"""Arabic and Latin text normalization and regex matching utilities.

Provides deterministic normalization for Arabic and English text:
- Stripping tashkeel (diacritics) and tatweel (kashida)
- Normalizing alef variants (أ, إ, آ, ٱ -> ا)
- Normalizing ya and alef maqsura (ى -> ي)
- Normalizing ta marbuta (ة -> ه)
- Mapping Arabic-Indic and Eastern Arabic digits to ASCII 0-9
- Lowercasing Latin characters
- Prefix-aware clitic matching for Arabic keywords (و, ف, ب, ل, ك, ال, لل, وال, بال, كال, فال)
- Strict word-boundary matching for Latin keywords
"""

import re

# Diacritics (tashkeel): Fathatan, Dammatan, Kasratan, Fatha, Damma, Kasra, Shadda, Sukun, Superscript Alef
TASHKEEL_RE = re.compile(r"[\u064B-\u065F\u0670]")
TATWEEL_CHAR = "\u0640"

# Digit translation tables
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Arabic character range
ARABIC_CHAR_RE = re.compile(r"[\u0600-\u06FF]")

# Arabic clitic prefix group: و ف ب ل ك ال لل وال بال كال فال
# Ordered longest-first in regex to ensure greedy matching of compound prefixes
ARABIC_PREFIX_PATTERN = r"(?:وال|بال|كال|فال|لل|ال|[وفبلك])?"


def normalize_text(text: str | None) -> str:
    """Normalize Arabic and Latin text deterministically.

    1. Convert None to empty string
    2. Lowercase Latin characters
    3. Strip tashkeel and tatweel
    4. Normalize alef variants (أ, إ, آ, ٱ -> ا)
    5. Normalize alef maqsura (ى -> ي)
    6. Normalize ta marbuta (ة -> ه)
    7. Convert Arabic-Indic and Eastern digits to ASCII digits
    8. Collapse repeated whitespace and strip
    """
    if not text:
        return ""

    # Lowercase Latin characters
    res = text.lower()

    # Strip tashkeel and tatweel
    res = TASHKEEL_RE.sub("", res)
    res = res.replace(TATWEEL_CHAR, "")

    # Normalize Alef variants
    res = re.sub(r"[أإآٱ]", "ا", res)

    # Normalize Ya / Alef Maqsura
    res = res.replace("ى", "ي")

    # Normalize Ta Marbuta
    res = res.replace("ة", "ه")

    # Translate Arabic-Indic and Eastern Persian digits to standard ASCII digits
    res = res.translate(ARABIC_INDIC_DIGITS)

    # Normalize whitespace
    res = re.sub(r"\s+", " ", res).strip()
    return res


def is_arabic_text(text: str) -> bool:
    """Check if the text contains any Arabic characters."""
    return bool(ARABIC_CHAR_RE.search(text))


def compile_keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a normalized keyword into a boundary-aware regex.

    - Latin keywords use strict word boundaries: (?<![a-zA-Z0-9_])kw(?![a-zA-Z0-9_])
      This prevents 'Java' matching 'JavaScript' or 'py' matching 'python'.
    - Arabic keywords allow attached clitic prefixes (و, ف, ب, ل, ك, ال, لل, وال, بال, كال, فال)
      before words while strictly requiring word boundary after.
      This enables 'تصنيف' to match 'للتصنيف' and 'والتصنيف', and 'ذكاء اصطناعي'
      to match 'بالذكاء الاصطناعي'.
    """
    norm_kw = normalize_text(keyword)
    if not norm_kw:
        # Match nothing
        return re.compile(r"$^")

    if is_arabic_text(norm_kw):
        words = norm_kw.split()
        word_patterns: list[str] = []
        for word in words:
            if is_arabic_text(word):
                # If word explicitly starts with "ال" and has stem length >= 3 (word length >= 5)
                # Words like "الي" (from آلي) have 3 letters and are stems, not definite article + 1 letter!
                stem = word[2:] if word.startswith("ال") and len(word) >= 5 else word
                word_patterns.append(rf"{ARABIC_PREFIX_PATTERN}{re.escape(stem)}")
            else:
                word_patterns.append(re.escape(word))

        combined = r"\s+".join(word_patterns)
        pattern = rf"(?<![\u0621-\u064A0-9a-zA-Z]){combined}(?![\u0621-\u064A0-9a-zA-Z])"
    else:
        # Latin / English keyword: strict ASCII word boundaries
        escaped = re.escape(norm_kw)
        pattern = rf"(?<![a-zA-Z0-9_]){escaped}(?![a-zA-Z0-9_])"

    return re.compile(pattern, re.IGNORECASE)

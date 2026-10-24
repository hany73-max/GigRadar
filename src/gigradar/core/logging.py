"""Structured logging setup using structlog and standard logging with secret redaction."""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

# Redaction patterns for sensitive tokens, headers, query parameters, and API keys
REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Telegram bot tokens: bot<digits>:<token>
    (re.compile(r"(bot\d+:)[A-Za-z0-9_-]+", re.IGNORECASE), r"\1[REDACTED]"),
    # Authorization: Bearer ... header
    (re.compile(r"(Authorization\s*:\s*Bearer\s+)[^\s,'\"]+", re.IGNORECASE), r"\1[REDACTED]"),
    # x-goog-api-key header
    (re.compile(r"(x-goog-api-key\s*[:=]\s*['\"]?)[^\s,'\"]+", re.IGNORECASE), r"\1[REDACTED]"),
    # Sensitive query parameters or bare key=... / token=... assignments
    (
        re.compile(
            r"((?:[?&]|\b)(?:api[_-]?key|token|key|secret)\s*[:=]\s*['\"]?)[^\s,'\"&]+",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
    # Google API key patterns: AIza followed by 35 URL-safe characters
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "[REDACTED]"),
    # Google API key patterns: AQ. followed by at least 20 URL-safe characters
    (re.compile(r"\bAQ\.[0-9A-Za-z_-]{20,}\b"), "[REDACTED]"),
)

_CONFIGURED_SECRETS: set[str] = set()


def register_configured_secrets(secrets: list[str | None]) -> None:
    """Register literal secrets to be redacted, ignoring empty, short, or placeholder values."""
    global _CONFIGURED_SECRETS
    from gigradar.core.gemini_verifier import is_placeholder

    for s in secrets:
        if s is None:
            continue
        clean = s.strip()
        if len(clean) >= 8 and not is_placeholder(clean):
            _CONFIGURED_SECRETS.add(clean)


def configure_secrets_from_settings() -> None:
    """Safely populate literal secrets from settings if available (without raising)."""
    try:
        from gigradar.core.settings import get_settings

        settings = get_settings()
        secrets = [
            settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None,
            settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else None,
            (
                settings.freelancer_oauth_token.get_secret_value()
                if settings.freelancer_oauth_token
                else None
            ),
        ]
        register_configured_secrets(secrets)
    except Exception:
        # Must never crash if settings or .env cannot be loaded
        pass


def redact_secrets(text: str) -> str:
    """Mask bot tokens, headers, API keys, query parameters, and literal secrets in text."""
    if not isinstance(text, str):
        return text
    result = text
    # 1. Literal configured secrets
    for secret in _CONFIGURED_SECRETS:
        if secret and len(secret) >= 8:
            result = result.replace(secret, "[REDACTED]")
    # 2. Pattern replacements
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _redact_value(val: Any) -> Any:
    """Recursively redact strings in dicts, lists, and tuples."""
    if isinstance(val, str):
        return redact_secrets(val)
    if isinstance(val, dict):
        return {k: _redact_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_redact_value(v) for v in val]
    if isinstance(val, tuple):
        return tuple(_redact_value(v) for v in val)
    return val


def structlog_redaction_processor(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Structlog processor to sanitize sensitive tokens in event dictionary."""
    return _redact_value(event_dict)  # type: ignore[no-any-return]


class RedactingFilter(logging.Filter):
    """Stdlib logging filter redacting messages, arguments, and exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_redact_value(v) for v in record.args)
        if record.exc_text:
            record.exc_text = redact_secrets(record.exc_text)
        return True


class RedactingProcessorFormatter(structlog.stdlib.ProcessorFormatter):
    """ProcessorFormatter ensuring all output lines (including stack traces) are redacted."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_secrets(formatted)


def setup_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    """Configure secret-safe structured logging for GigRadar."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    configure_secrets_from_settings()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog_redaction_processor,
    ]

    if log_format.lower() == "json":
        formatter_processor: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        from structlog.dev import ConsoleRenderer, RichTracebackFormatter

        formatter_processor = ConsoleRenderer(
            colors=sys.stderr.isatty(),
            exception_formatter=RichTracebackFormatter(
                show_locals=False,
                color_system="auto" if sys.stderr.isatty() else "standard",
            ),
        )

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = RedactingProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            formatter_processor,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.addFilter(RedactingFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Silence noisy HTTP and DB migration loggers to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Obtain a structured logger instance."""
    return structlog.get_logger(name)

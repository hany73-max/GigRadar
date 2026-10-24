"""Structured logging setup using structlog and standard logging with secret redaction."""

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

# Redaction patterns for sensitive tokens and query parameters
REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Telegram bot tokens: bot<digits>:<token>
    (re.compile(r"(bot\d+:)[A-Za-z0-9_-]+", re.IGNORECASE), r"\1[REDACTED]"),
    # Sensitive query parameters: key=..., token=..., api_key=..., secret=...
    (
        re.compile(r"([?&](?:api[_-]?key|token|key|secret)=)[^&\s'\"]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
)


def redact_secrets(text: str) -> str:
    """Mask bot tokens and secret query values in text strings."""
    if not isinstance(text, str):
        return text
    result = text
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
        formatter_processor = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

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

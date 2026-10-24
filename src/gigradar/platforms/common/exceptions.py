"""Platform-specific exceptions and error types."""

from typing import Any


class PlatformError(Exception):
    """Base exception for all platform scraper and API errors."""

    def __init__(self, message: str, platform: str | None = None, **kwargs: Any) -> None:
        super().__init__(message)
        self.message = message
        self.platform = platform
        self.details = kwargs


class BlockedByBotProtection(PlatformError):
    """Raised when an HTTP response is identified as a WAF challenge, Cloudflare block, or CAPTCHA."""

    def __init__(
        self,
        message: str,
        platform: str | None = None,
        status_code: int | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, platform=platform, **kwargs)
        self.status_code = status_code
        self.reason = reason

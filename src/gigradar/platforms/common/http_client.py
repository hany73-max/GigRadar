"""Polite HTTP client layer with per-platform rate limiting, jitter, and tenacity backoff."""

import asyncio
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Async per-platform rate limiter with jitter support."""

    def __init__(
        self,
        min_interval_seconds: float = 2.0,
        jitter_min_seconds: float = 0.5,
        jitter_max_seconds: float = 2.0,
    ) -> None:
        self.min_interval = min_interval_seconds
        self.jitter_min = jitter_min_seconds
        self.jitter_max = jitter_max_seconds
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait until it is safe to make the next request, including jitter."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            jitter = random.uniform(self.jitter_min, self.jitter_max)
            target_wait = max(0.0, self.min_interval - elapsed) + jitter

            if target_wait > 0:
                await asyncio.sleep(target_wait)

            self._last_request_time = asyncio.get_event_loop().time()


def _is_retryable_exception(exc: BaseException) -> bool:
    """Determine whether an HTTP error is transient and retryable."""
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        # 429 Too Many Requests, 500, 502, 503 Service Unavailable, 504 Gateway Timeout
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Extract retry delay from 429/503 Retry-After header if present."""
    header = response.headers.get("retry-after")
    if not header:
        return None

    header = header.strip()
    # Try integer seconds first
    try:
        seconds = float(header)
        return max(0.0, seconds)
    except ValueError:
        pass

    # Try HTTP-date format
    try:
        dt = parsedate_to_datetime(header)
        now = datetime.now(UTC)
        diff = (dt - now).total_seconds()
        return max(0.0, diff)
    except Exception:
        return None


class PoliteHttpClient:
    """Polite HTTP client wrapping httpx.AsyncClient with rate limiting and retries."""

    def __init__(
        self,
        user_agent: str = "GigRadar/0.1.0",
        timeout_seconds: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        max_retries: int = 3,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }
        if extra_headers:
            headers.update(extra_headers)

        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
        )
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Perform polite GET request with rate limiting and exponential backoff."""
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=10.0),
            retry=retry_if_exception(_is_retryable_exception),
            reraise=True,
        )

        async for attempt in retrying:
            with attempt:
                await self.rate_limiter.wait()
                logger.debug("polite_http_get", url=url, attempt=attempt.retry_state.attempt_number)
                response = await self._client.get(url, **kwargs)

                # Check if we got 429/503 with Retry-After header
                if response.status_code in {429, 503}:
                    retry_after = _parse_retry_after(response)
                    if retry_after is not None and retry_after > 0:
                        logger.warning(
                            "http_retry_after_received",
                            status=response.status_code,
                            retry_after=retry_after,
                            url=url,
                        )
                        await asyncio.sleep(retry_after)
                    response.raise_for_status()

                response.raise_for_status()
                return response

        raise RuntimeError("Unreachable: retrying should return or reraise")

    async def close(self) -> None:
        """Close internal HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "PoliteHttpClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

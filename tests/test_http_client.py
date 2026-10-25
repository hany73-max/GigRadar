"""Unit tests for PoliteHttpClient and RateLimiter."""

import time

import httpx
import pytest

from gigradar.platforms.common.http_client import (
    PoliteHttpClient,
    RateLimiter,
    _parse_retry_after,
)


@pytest.mark.asyncio
async def test_rate_limiter_spacing() -> None:
    limiter = RateLimiter(
        min_interval_seconds=0.1, jitter_min_seconds=0.01, jitter_max_seconds=0.05
    )
    t0 = time.monotonic()
    await limiter.wait()
    await limiter.wait()
    t1 = time.monotonic()
    assert (t1 - t0) >= 0.1


@pytest.mark.asyncio
async def test_rate_limiter_skips_jitter_on_first_and_idle_requests() -> None:
    import asyncio

    limiter = RateLimiter(
        min_interval_seconds=0.05,
        jitter_min_seconds=0.15,
        jitter_max_seconds=0.25,
        idle_threshold_seconds=0.1,
    )

    # 1. First request ever: immediate (no jitter delay)
    t0 = time.monotonic()
    await limiter.wait()
    t1 = time.monotonic()
    assert (t1 - t0) < 0.05, "First request must not suffer jitter delay"

    # 2. Consecutive request: must wait for min_interval + jitter
    t2 = time.monotonic()
    await limiter.wait()
    t3 = time.monotonic()
    assert (t3 - t2) >= 0.15, "Consecutive request must wait for pacing + jitter"

    # 3. Simulate idle period by waiting past idle_threshold
    await asyncio.sleep(0.12)

    # 4. Request after idle period: immediate (no jitter delay)
    t4 = time.monotonic()
    await limiter.wait()
    t5 = time.monotonic()
    assert (t5 - t4) < 0.05, "Request after idle period must not suffer jitter delay"


def test_parse_retry_after_seconds() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "15"})
    assert _parse_retry_after(resp) == 15.0


def test_parse_retry_after_capped() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "300"})
    # Default cap is 120
    assert _parse_retry_after(resp) == 120.0
    # Custom cap
    assert _parse_retry_after(resp, max_retry_after_seconds=60.0) == 60.0


def test_rate_limiter_none_sentinel() -> None:
    limiter = RateLimiter()
    assert limiter._last_request_time is None


def test_parse_retry_after_missing() -> None:
    resp = httpx.Response(200)
    assert _parse_retry_after(resp) is None


@pytest.mark.asyncio
async def test_polite_http_client_get_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Hello world")

    transport = httpx.MockTransport(handler)
    client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    client._client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://example.com/test")
    assert response.status_code == 200
    assert response.text == "Hello world"
    await client.close()


@pytest.mark.asyncio
async def test_polite_http_client_retries_on_503() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, text="Recovered")

    transport = httpx.MockTransport(handler)
    client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        ),
        max_retries=3,
    )
    client._client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://example.com/flake")
    assert response.status_code == 200
    assert response.text == "Recovered"
    assert attempts == 2
    await client.close()

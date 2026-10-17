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
    limiter = RateLimiter(min_interval_seconds=0.1, jitter_min_seconds=0.01, jitter_max_seconds=0.05)
    t0 = time.monotonic()
    await limiter.wait()
    await limiter.wait()
    t1 = time.monotonic()
    assert (t1 - t0) >= 0.1


def test_parse_retry_after_seconds() -> None:
    resp = httpx.Response(429, headers={"Retry-After": "15"})
    assert _parse_retry_after(resp) == 15.0


def test_parse_retry_after_missing() -> None:
    resp = httpx.Response(200)
    assert _parse_retry_after(resp) is None


@pytest.mark.asyncio
async def test_polite_http_client_get_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Hello world")

    transport = httpx.MockTransport(handler)
    client = PoliteHttpClient(
        rate_limiter=RateLimiter(min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0)
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
        rate_limiter=RateLimiter(min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0),
        max_retries=3,
    )
    client._client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://example.com/flake")
    assert response.status_code == 200
    assert response.text == "Recovered"
    assert attempts == 2
    await client.close()

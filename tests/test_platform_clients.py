"""Unit tests for MostaqlClient and KhamsatClient."""

from pathlib import Path

import httpx
import pytest

from gigradar.platforms.base import PlatformClient
from gigradar.platforms.common.http_client import PoliteHttpClient, RateLimiter
from gigradar.platforms.khamsat.client import KhamsatClient
from gigradar.platforms.mostaql.client import MostaqlClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"


def test_platform_clients_implement_protocol() -> None:
    mostaql = MostaqlClient()
    khamsat = KhamsatClient()
    assert isinstance(mostaql, PlatformClient)
    assert isinstance(khamsat, PlatformClient)


@pytest.mark.asyncio
async def test_mostaql_client_list_and_detail() -> None:
    listing_html = (FIXTURES_DIR / "mostaql_listing.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "mostaql_detail.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if "projects" in str(request.url):
            return httpx.Response(200, text=listing_html)
        return httpx.Response(200, text=detail_html)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0)
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = MostaqlClient(http_client=http_client)
    client.config.max_pages_per_run = 1
    stubs = await client.list_new_gigs()
    assert len(stubs) == 25

    stub = stubs[0]
    gig = await client.fetch_gig_detail(stub)
    assert gig.platform_id == "mostaql"
    assert gig.external_id == "1286262"  # from fixture
    assert gig.budget_min == 50.0

    health = await client.health_check()
    assert health.is_healthy is True
    await client.close()


@pytest.mark.asyncio
async def test_khamsat_client_list_and_detail() -> None:
    listing_html = (FIXTURES_DIR / "khamsat_listing.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=listing_html)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0)
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = KhamsatClient(http_client=http_client)
    client.config.max_pages_per_run = 1
    stubs = await client.list_new_gigs()
    assert len(stubs) == 25

    stub = stubs[0]
    assert stub.bids_count is None
    gig = await client.fetch_gig_detail(stub)
    assert gig.platform_id == "khamsat"
    assert gig.external_id == stub.external_id
    assert gig.title == stub.title
    assert gig.bids_count is None

    health = await client.health_check()
    assert health.is_healthy is True
    await client.close()


@pytest.mark.asyncio
async def test_mostaql_health_check_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0),
        max_retries=1,
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = MostaqlClient(http_client=http_client)
    health = await client.health_check()
    assert health.is_healthy is False
    assert "Health check failed" in health.message
    await client.close()

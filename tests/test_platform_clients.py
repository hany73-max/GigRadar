"""Unit tests for MostaqlClient and KhamsatClient."""

from pathlib import Path

import httpx
import pytest

from gigradar.platforms.base import PlatformClient
from gigradar.platforms.common.http_client import PoliteHttpClient, RateLimiter
from gigradar.platforms.freelancer.client import FreelancerClient
from gigradar.platforms.khamsat.client import KhamsatClient
from gigradar.platforms.mostaql.client import MostaqlClient

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "html"
JSON_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "json"


def test_platform_clients_implement_protocol() -> None:
    mostaql = MostaqlClient()
    khamsat = KhamsatClient()
    freelancer = FreelancerClient()
    assert isinstance(mostaql, PlatformClient)
    assert isinstance(khamsat, PlatformClient)
    assert isinstance(freelancer, PlatformClient)


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
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
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
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
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
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        ),
        max_retries=1,
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = MostaqlClient(http_client=http_client)
    health = await client.health_check()
    assert health.is_healthy is False
    assert "Health check failed" in health.message
    await client.close()


@pytest.mark.asyncio
async def test_freelancer_client_list_and_detail() -> None:
    active_json = (JSON_FIXTURES_DIR / "freelancer_projects.json").read_text(encoding="utf-8")
    detail_json = (JSON_FIXTURES_DIR / "freelancer_single_project.json").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("accept") == "application/json"
        url_str = str(request.url)
        if "projects/active" in url_str:
            return httpx.Response(200, text=active_json)
        return httpx.Response(200, text=detail_json)

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        )
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = FreelancerClient(http_client=http_client)
    stubs = await client.list_new_gigs()
    # 8 total in fixture - 3 excluded (NDA, local, recruiter) = 5 valid stubs
    assert len(stubs) == 5

    first_stub = stubs[0]
    assert first_stub.platform_id == "freelancer"
    assert first_stub.external_id == "40773380"
    assert first_stub.bids_count == 31

    # Fetch detail (cached)
    gig = await client.fetch_gig_detail(first_stub)
    assert gig.platform_id == "freelancer"
    assert gig.external_id == "40773380"
    assert gig.currency == "GBP"
    assert gig.budget_min_usd == 13.33
    assert gig.budget_max_usd == 26.66
    assert gig.budget_usd_est == 20.0

    health = await client.health_check()
    assert health.is_healthy is True
    await client.close()


@pytest.mark.asyncio
async def test_freelancer_health_check_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    http_client = PoliteHttpClient(
        rate_limiter=RateLimiter(
            min_interval_seconds=0.0, jitter_min_seconds=0.0, jitter_max_seconds=0.0
        ),
        max_retries=1,
    )
    http_client._client = httpx.AsyncClient(transport=transport)

    client = FreelancerClient(http_client=http_client)
    health = await client.health_check()
    assert health.is_healthy is False
    assert "Health check failed" in health.message or "returned HTTP 500" in health.message
    await client.close()

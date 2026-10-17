"""Khamsat platform client implementing PlatformClient."""

from datetime import datetime
from typing import Any

import structlog

from gigradar.core.config_loader import load_platforms_config
from gigradar.core.config_models import PlatformSettings
from gigradar.core.models import Gig, GigStub, HealthReport
from gigradar.platforms.common.http_client import PoliteHttpClient, RateLimiter
from gigradar.platforms.khamsat.parser import parse_khamsat_gig_from_stub, parse_khamsat_listing

logger = structlog.get_logger(__name__)


class KhamsatClient:
    """Scraper client for Khamsat buyer requests.

    Per project architectural decision, Khamsat detail pages sit behind an AWS WAF
    challenge and are intentionally not fetched. All fields are parsed from listing pages.
    """

    name: str = "khamsat"

    def __init__(
        self,
        config: PlatformSettings | None = None,
        http_client: PoliteHttpClient | None = None,
    ) -> None:
        if config is None:
            platforms_cfg = load_platforms_config()
            self.config = platforms_cfg.platforms.get(
                "khamsat",
                PlatformSettings(
                    name="Khamsat",
                    type="scraper",
                    base_url="https://khamsat.com",
                    listing_url="https://khamsat.com/community/requests",
                    jitter_seconds_min=1,
                    jitter_seconds_max=3,
                    max_pages_per_run=2,
                    timeout_seconds=30,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                ),
            )
        else:
            self.config = config

        if http_client is None:
            rate_limiter = RateLimiter(
                min_interval_seconds=1.5,
                jitter_min_seconds=float(self.config.jitter_seconds_min),
                jitter_max_seconds=float(self.config.jitter_seconds_max),
            )
            self._http = PoliteHttpClient(
                user_agent=self.config.user_agent,
                timeout_seconds=float(self.config.timeout_seconds),
                rate_limiter=rate_limiter,
            )
            self._owns_http = True
        else:
            self._http = http_client
            self._owns_http = False

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        """Fetch buyer request stubs from Khamsat listing pages up to max_pages_per_run."""
        base_listing_url = self.config.listing_url or f"{self.config.base_url}/community/requests"
        stubs: list[GigStub] = []

        max_pages = max(1, self.config.max_pages_per_run)

        for page in range(1, max_pages + 1):
            url = base_listing_url if page == 1 else f"{base_listing_url}?page={page}"
            logger.info("khamsat_fetching_listing", page=page, url=url)

            response = await self._http.get(url)
            page_stubs = parse_khamsat_listing(response.text, base_url=self.config.base_url)

            if not page_stubs:
                break

            reached_since = False
            for stub in page_stubs:
                if since and stub.posted_at and stub.posted_at < since:
                    reached_since = True
                    break
                stubs.append(stub)

            if reached_since:
                break

        logger.info("khamsat_listing_completed", count=len(stubs))
        return stubs

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        """Convert a Khamsat stub to a Gig without fetching detail pages (AWS WAF protected)."""
        logger.info("khamsat_resolving_gig_from_stub", external_id=stub.external_id, url=stub.url)
        return parse_khamsat_gig_from_stub(stub)

    async def health_check(self) -> HealthReport:
        """Verify Khamsat listing page structure to detect layout drift."""
        url = self.config.listing_url or f"{self.config.base_url}/community/requests"
        try:
            response = await self._http.get(url)
            stubs = parse_khamsat_listing(response.text, base_url=self.config.base_url)
            if not stubs:
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message="Zero requests parsed from listing; layout may have changed",
                )
            first = stubs[0]
            if not (first.external_id and first.title and first.url):
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message="Parsed request missing essential fields (id, title, url)",
                )
            return HealthReport(
                platform_id=self.name,
                is_healthy=True,
                message=f"Healthy: parsed {len(stubs)} request stubs successfully",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("khamsat_health_check_failed", error=str(exc))
            return HealthReport(
                platform_id=self.name,
                is_healthy=False,
                message=f"Health check failed with error: {exc}",
            )

    async def close(self) -> None:
        """Clean up HTTP client if owned."""
        if self._owns_http:
            await self._http.close()

    async def __aenter__(self) -> "KhamsatClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

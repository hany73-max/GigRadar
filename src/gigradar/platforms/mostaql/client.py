"""Mostaql platform client implementing PlatformClient."""

from datetime import datetime
from typing import Any

import structlog

from gigradar.core.config_loader import load_platforms_config
from gigradar.core.config_models import PlatformSettings
from gigradar.core.models import Gig, GigStub, HealthReport
from gigradar.platforms.common.http_client import (
    PoliteHttpClient,
    RateLimiter,
    detect_html_bot_protection,
)
from gigradar.platforms.mostaql.parser import parse_mostaql_detail, parse_mostaql_listing

logger = structlog.get_logger(__name__)


class MostaqlClient:
    """Scraper client for Mostaql projects."""

    name: str = "mostaql"

    def __init__(
        self,
        config: PlatformSettings | None = None,
        http_client: PoliteHttpClient | None = None,
    ) -> None:
        if config is None:
            platforms_cfg = load_platforms_config()
            self.config = platforms_cfg.platforms.get(
                "mostaql",
                PlatformSettings(
                    name="Mostaql",
                    type="scraper",
                    base_url="https://mostaql.com",
                    listing_url="https://mostaql.com/projects",
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
        """Fetch project stubs from Mostaql listing pages up to max_pages_per_run."""
        base_listing_url = self.config.listing_url or f"{self.config.base_url}/projects"
        stubs: list[GigStub] = []

        max_pages = max(1, self.config.max_pages_per_run)

        for page in range(1, max_pages + 1):
            url = base_listing_url if page == 1 else f"{base_listing_url}?page={page}"
            logger.info("mostaql_fetching_listing", page=page, url=url)

            response = await self._http.get(url)
            page_stubs = parse_mostaql_listing(response.text, base_url=self.config.base_url)

            if not page_stubs:
                detect_html_bot_protection(response.text, platform=self.name, url=url)
                break

            reached_since = False
            for stub in page_stubs:
                if since and stub.posted_at and stub.posted_at < since:
                    reached_since = True
                    break
                stubs.append(stub)

            if reached_since:
                break

        logger.info("mostaql_listing_completed", count=len(stubs))
        return stubs

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        """Fetch full project detail for a Mostaql stub."""
        logger.info("mostaql_fetching_detail", external_id=stub.external_id, url=stub.url)
        response = await self._http.get(stub.url)
        try:
            gig = parse_mostaql_detail(response.text, stub=stub, base_url=self.config.base_url)
            return gig
        except ValueError:
            detect_html_bot_protection(response.text, platform=self.name, url=stub.url)
            raise

    async def health_check(self) -> HealthReport:
        """Verify Mostaql listing page structure to detect layout drift."""
        url = self.config.listing_url or f"{self.config.base_url}/projects"
        try:
            response = await self._http.get(url)
            stubs = parse_mostaql_listing(response.text, base_url=self.config.base_url)
            if not stubs:
                detect_html_bot_protection(response.text, platform=self.name, url=url)
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message="Zero projects parsed from listing; layout may have changed",
                )
            first = stubs[0]
            if not (first.external_id and first.title and first.url):
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message="Parsed project missing essential fields (id, title, url)",
                )
            return HealthReport(
                platform_id=self.name,
                is_healthy=True,
                message=f"Healthy: parsed {len(stubs)} project stubs successfully",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("mostaql_health_check_failed", error=str(exc))
            return HealthReport(
                platform_id=self.name,
                is_healthy=False,
                message=f"Health check failed with error: {exc}",
            )

    async def close(self) -> None:
        """Clean up HTTP client if owned."""
        if self._owns_http:
            await self._http.close()

    async def __aenter__(self) -> "MostaqlClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

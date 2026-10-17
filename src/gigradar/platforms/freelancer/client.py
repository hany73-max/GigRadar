"""Freelancer.com platform client implementing PlatformClient via official REST API."""

from datetime import UTC, datetime
from typing import Any

import structlog

from gigradar.core.config_loader import load_platforms_config
from gigradar.core.config_models import PlatformSettings
from gigradar.core.models import Gig, GigStub, HealthReport
from gigradar.platforms.common.http_client import PoliteHttpClient, RateLimiter
from gigradar.platforms.freelancer.parser import (
    is_excluded_project,
    parse_freelancer_project,
    parse_freelancer_stub,
)

logger = structlog.get_logger(__name__)

# Discovered & verified Freelancer skill IDs (Master Prompt 6.1b item 4)
FREELANCER_SKILL_IDS: dict[str, int] = {
    "python": 13,
    "machine_learning": 292,
    "deep_learning": 1601,
    "data_science": 761,
    "nlp": 2833,
    "computer_vision": 1558,
    "web_scraping": 95,
    "sql": 68,
    "data_processing": 36,
    "data_mining": 334,
}


class FreelancerClient:
    """Official REST API client for Freelancer.com."""

    name: str = "freelancer"

    def __init__(
        self,
        config: PlatformSettings | None = None,
        http_client: PoliteHttpClient | None = None,
        skill_ids: list[int] | None = None,
    ) -> None:
        if config is None:
            platforms_cfg = load_platforms_config()
            self.config = platforms_cfg.platforms.get(
                "freelancer",
                PlatformSettings(
                    name="Freelancer",
                    type="api",
                    base_url="https://www.freelancer.com",
                    base_api_url="https://www.freelancer.com/api/projects/0.1/",
                    jitter_seconds_min=1,
                    jitter_seconds_max=3,
                    max_pages_per_run=1,
                    timeout_seconds=30,
                    user_agent="GigRadar/0.1.0",
                ),
            )
        else:
            self.config = config

        self.skill_ids = skill_ids if skill_ids is not None else list(FREELANCER_SKILL_IDS.values())
        self._cached_gigs: dict[str, Gig] = {}

        if http_client is None:
            rate_limiter = RateLimiter(
                min_interval_seconds=1.0,
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

    @property
    def api_root(self) -> str:
        base = self.config.base_api_url or f"{self.config.base_url}/api/projects/0.1/"
        return base if base.endswith("/") else f"{base}/"

    async def list_new_gigs(self, since: datetime | None = None) -> list[GigStub]:
        """Fetch active projects matching skills, newest first, deduplicated and filtered."""
        active_endpoint = f"{self.api_root}projects/active/"
        logger.info(
            "freelancer_fetching_active_projects",
            url=active_endpoint,
            skills_count=len(self.skill_ids),
        )

        # Query 1: Skill IDs query
        params: list[tuple[str, str | int]] = [
            ("sort_field", "time_updated"),
            ("limit", max(10, min(100, 25 * max(1, self.config.max_pages_per_run)))),
            ("full_description", "true"),
            ("job_details", "true"),
        ]
        if since:
            params.append(("from_time", int(since.timestamp())))

        for skill_id in self.skill_ids:
            params.append(("jobs[]", skill_id))

        response = await self._http.get(active_endpoint, params=params)
        payload = response.json()
        raw_projects = payload.get("result", {}).get("projects", [])

        stubs: list[GigStub] = []
        seen_ids: set[str] = set()

        for raw_proj in raw_projects:
            if not isinstance(raw_proj, dict):
                continue

            proj_id = str(raw_proj.get("id"))
            if not proj_id or proj_id in seen_ids:
                continue

            # Server-side safety exclusions (contests, NDA, local, recruiter)
            excluded, reason = is_excluded_project(raw_proj)
            if excluded:
                logger.debug("freelancer_project_excluded", project_id=proj_id, reason=reason)
                continue

            stub = parse_freelancer_stub(raw_proj)
            if since and stub.posted_at and stub.posted_at < since:
                continue

            seen_ids.add(proj_id)
            stubs.append(stub)

            # Cache the parsed Gig so fetch_gig_detail requires zero additional network calls
            self._cached_gigs[proj_id] = parse_freelancer_project(raw_proj)

        # Ensure newest projects are returned first
        stubs.sort(key=lambda s: s.posted_at or datetime.min.replace(tzinfo=UTC), reverse=True)

        logger.info("freelancer_listing_completed", count=len(stubs))
        return stubs

    async def fetch_gig_detail(self, stub: GigStub) -> Gig:
        """Fetch full project detail for a Freelancer stub."""
        if stub.external_id in self._cached_gigs:
            return self._cached_gigs[stub.external_id]

        detail_endpoint = f"{self.api_root}projects/{stub.external_id}/"
        logger.info("freelancer_fetching_detail", external_id=stub.external_id, url=detail_endpoint)

        response = await self._http.get(
            detail_endpoint,
            params=[("full_description", "true"), ("job_details", "true")],
        )
        data = response.json()
        raw_proj = data.get("result")
        if not isinstance(raw_proj, dict):
            raise ValueError(
                f"Invalid Freelancer project detail response for ID {stub.external_id}"
            )

        gig = parse_freelancer_project(raw_proj)
        self._cached_gigs[stub.external_id] = gig
        return gig

    async def health_check(self) -> HealthReport:
        """Verify Freelancer active projects API connectivity and response structure."""
        active_endpoint = f"{self.api_root}projects/active/"
        try:
            response = await self._http.get(active_endpoint, params=[("limit", 1)])
            if response.status_code != 200:
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message=f"Freelancer API returned HTTP {response.status_code}",
                )

            data = response.json()
            projects = data.get("result", {}).get("projects")
            if not isinstance(projects, list) or len(projects) == 0:
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message="Freelancer API returned empty projects array",
                )

            p0 = projects[0]
            if not (p0.get("id") and p0.get("title")):
                return HealthReport(
                    platform_id=self.name,
                    is_healthy=False,
                    message="Freelancer API project missing required id or title",
                )

            return HealthReport(
                platform_id=self.name,
                is_healthy=True,
                message=f"Healthy: verified Freelancer active projects API (sample ID {p0.get('id')})",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("freelancer_health_check_failed", error=str(exc))
            return HealthReport(
                platform_id=self.name,
                is_healthy=False,
                message=f"Health check failed with error: {exc}",
            )

    async def close(self) -> None:
        """Clean up HTTP client if owned."""
        if self._owns_http:
            await self._http.close()

    async def __aenter__(self) -> "FreelancerClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
